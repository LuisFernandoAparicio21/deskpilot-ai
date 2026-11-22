"""Command-line entry point for DeskPilot AI.

Every pipeline step runs through a subcommand:

    python main.py generate-data | load-db | index | serve | mcp | eval | export-openapi

Subcommands without a handler yet only report which task will implement them and exit
with code 2. Implemented so far: ``generate-data`` (T9), ``load-db`` (T10), ``index`` (T14)
``serve`` (T16), ``mcp`` (T18), ``export-openapi`` (T19) and ``eval`` (T21).
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Callable, Sequence
from pathlib import Path

from src.ingestion.documents import DocumentError
from src.ingestion.sqlite_loader import MissingDataError, load_sqlite
from src.ingestion.ticket_generator import generate_dataset
from src.utils.config import PROJECT_ROOT, ConfigError, load_settings
from src.utils.db import SQL_DIR, format_table, list_query_files, run_sql_file, sqlite_connection
from src.utils.logging import configure_logging_from_settings

EXIT_OK = 0
EXIT_CONFIG_ERROR = 1
EXIT_NOT_IMPLEMENTED = 2
EXIT_DATA_ERROR = 3

DEFAULT_EVAL_CASES = PROJECT_ROOT / "tests" / "eval" / "cases.csv"
DEFAULT_EVAL_OUT = PROJECT_ROOT / "tests" / "eval" / "results.csv"
DEFAULT_OPENAPI_OUT = PROJECT_ROOT / "integrations" / "copilot_studio" / "openapi.json"
SQL_SUMMARY_MAX_ROWS = 10  # rows printed per query by ``load-db --run-sql``

# Subcommand -> (help text, task that implements it).
SUBCOMMANDS: dict[str, tuple[str, str]] = {
    "generate-data": ("Generate the synthetic ticket dataset (seeded).", "T9"),
    "load-db": ("Load the generated tickets into the local SQLite database.", "T10"),
    "index": ("Chunk, embed and index the knowledge base into the vector database.", "T14"),
    "serve": ("Start the FastAPI service.", "T16"),
    "mcp": ("Start the MCP server (stdio by default, or streamable HTTP).", "T18"),
    "eval": ("Run the agent evaluation cases and save the results.", "T21"),
    "export-openapi": ("Export the Swagger 2.0 JSON for Copilot Studio.", "T19"),
}


def _non_negative_int(value: str) -> int:
    number = int(value)
    if number < 0:
        raise argparse.ArgumentTypeError(f"must be >= 0, got {number}")
    return number


def _positive_int(value: str) -> int:
    number = int(value)
    if number < 1:
        raise argparse.ArgumentTypeError(f"must be >= 1, got {number}")
    return number


def _display(path: Path) -> str:
    """Path relative to the project root when possible, for readable output."""
    try:
        return path.relative_to(PROJECT_ROOT).as_posix()
    except ValueError:
        return str(path)


def cmd_generate_data(args: argparse.Namespace) -> int:
    """Write tickets.csv, sucursales.csv and the 200-row systematic sample (T9, S3)."""
    try:
        settings = load_settings()
    except ConfigError as exc:
        print(f"generate-data: {exc}", file=sys.stderr)
        return EXIT_CONFIG_ERROR
    configure_logging_from_settings(settings, console=False)
    seed: int = settings.data.seed if args.seed is None else args.seed
    n: int = settings.data.n_tickets if args.n is None else args.n
    result = generate_dataset(
        seed, n, settings.paths.raw, settings.paths.sample, settings.sla_horas.model_dump()
    )
    stats = result.stats
    print(f"generate-data: seed={seed}")
    print(f"  {result.n_tickets} tickets -> {_display(result.tickets_path)}")
    print(f"  {result.n_sucursales} sucursales -> {_display(result.sucursales_path)}")
    print(f"  {result.sample_size} sample rows (systematic) -> {_display(result.sample_path)}")
    print(f"  repetitive share: {stats.repetitive_share:.1%}")
    print(f"  payday unlock ratio (days 14-16, 29-31): {stats.payday_unlock_ratio:.2f}x")
    print(
        f"  SLA met: metro {stats.sla_metro_pct:.1f}% vs foraneas {stats.sla_foranea_pct:.1f}%"
        f" (gap {stats.sla_gap_pp:.1f} pp)"
    )
    print(f"  english share: {stats.english_share:.1%}")
    print(f"  open tickets at snapshot: {stats.open_tickets}")
    return EXIT_OK


def run_business_queries(db_path: Path, sql_dir: Path = SQL_DIR) -> int:
    """Run the numbered queries of ``sql_dir`` and print each result as a table (RF-20)."""
    files = list_query_files(sql_dir)
    if not files:
        print(f"load-db: no queries found in {_display(sql_dir)}", file=sys.stderr)
        return EXIT_DATA_ERROR
    with sqlite_connection(db_path) as conn:
        for path in files:
            result = run_sql_file(conn, path)
            print()
            print(f"== {result.name} ({len(result.rows)} rows)")
            print(format_table(result.columns, result.rows, SQL_SUMMARY_MAX_ROWS))
    print()
    print(f"load-db: {len(files)} queries executed")
    return EXIT_OK


def cmd_load_db(args: argparse.Namespace) -> int:
    """Load the CSV files into SQLite and optionally run the 10 SQL queries (T10, S5)."""
    try:
        settings = load_settings()
    except ConfigError as exc:
        print(f"load-db: {exc}", file=sys.stderr)
        return EXIT_CONFIG_ERROR
    configure_logging_from_settings(settings, console=False)
    try:
        result = load_sqlite(settings.paths.raw, settings.paths.sqlite_db)
    except MissingDataError as exc:
        print(f"load-db: {exc}", file=sys.stderr)
        return EXIT_DATA_ERROR
    print(f"load-db: {_display(result.db_path)}")
    print(f"  {result.n_sucursales} rows -> sucursales")
    print(f"  {result.n_tickets} rows -> tickets")
    print("  0 rows -> tickets_nuevos (created empty)")
    if args.run_sql:
        return run_business_queries(result.db_path)
    return EXIT_OK


def cmd_index(args: argparse.Namespace) -> int:
    """Chunk, embed and index the knowledge base into a new index version (T14, S7, RF-15).

    Runs offline only: it builds ``paths.vectordb/<version>/`` and then swaps the
    ``CURRENT`` pointer, so a running API keeps answering and picks up the new version.
    """
    # Imported here: chromadb takes ~1 s to import and only this command needs it.
    from src.vectordb.indexer import IndexBuildError, build_index

    try:
        settings = load_settings()
    except ConfigError as exc:
        print(f"index: {exc}", file=sys.stderr)
        return EXIT_CONFIG_ERROR
    configure_logging_from_settings(settings, console=False)
    try:
        result = build_index(settings)
        # Download the cross-encoder here (build time), so serving needs no network.
        from src.retrieval.reranker import build_reranker

        reranker = build_reranker(settings)
        if reranker is not None:
            reranker.warm()
    except (DocumentError, IndexBuildError) as exc:
        print(f"index: {exc}", file=sys.stderr)
        return EXIT_DATA_ERROR
    embeddings = settings.embeddings
    print(f"index: {_display(result.path)}")
    print(f"  {result.n_articles} articles -> {result.n_chunks} chunks")
    model = embeddings.model if embeddings.provider == "fastembed" else "token hashing"
    print(f"  embeddings: {embeddings.provider} {model} (dim {result.dimension})")
    print(f"  CURRENT -> {result.version}")
    removed = ", ".join(result.removed) if result.removed else "none"
    print(f"  old versions removed: {removed}")
    print(f"  elapsed: {result.elapsed_s:.1f} s")
    return EXIT_OK


def cmd_serve(args: argparse.Namespace) -> int:
    """Start the FastAPI service (T16, S8). Fails fast on invalid config or a missing API key."""
    # Imported here: the API pulls in FastAPI, uvicorn and chromadb, only this command needs them.
    import uvicorn

    from src.api import create_app
    from src.utils.config import require_api_key

    try:
        settings = load_settings()
        require_api_key(settings)
    except ConfigError as exc:
        print(f"serve: {exc}", file=sys.stderr)
        return EXIT_CONFIG_ERROR
    configure_logging_from_settings(settings)
    host: str = args.host or settings.api.host
    port: int = args.port or settings.api.port
    app = create_app(settings)
    # log_config=None: uvicorn logs propagate to our JSON handlers; the access log is off
    # because the request middleware logs method, route and status without the query string.
    uvicorn.run(app, host=host, port=port, log_config=None, access_log=False, server_header=False)
    return EXIT_OK


def cmd_export_openapi(args: argparse.Namespace) -> int:
    """Write the Swagger 2.0 JSON that Copilot Studio accepts (T19, S8).

    Builds the app with placeholder services: no server, database, index or API key needed.
    """
    from src.api.openapi_export import DEFAULT_HOST, ExportError, export_swagger, write_swagger

    try:
        settings = load_settings()
        spec = export_swagger(settings, args.host or DEFAULT_HOST)
        out = Path(args.out) if args.out else DEFAULT_OPENAPI_OUT
        size = write_swagger(spec, out)
    except ConfigError as exc:
        print(f"export-openapi: {exc}", file=sys.stderr)
        return EXIT_CONFIG_ERROR
    except ExportError as exc:
        print(f"export-openapi: {exc}", file=sys.stderr)
        return EXIT_DATA_ERROR
    operations = [
        op["operationId"] for methods in spec["paths"].values() for op in methods.values()
    ]
    print(f"export-openapi: {_display(out)} (Swagger 2.0, {size} bytes)")
    print(f"  host: {spec['host']}  schemes: https  operations: {', '.join(operations)}")
    if spec["host"] == DEFAULT_HOST:
        print("  host is a placeholder: pass --host <your public host> before uploading")
    return EXIT_OK


def cmd_eval(args: argparse.Namespace) -> int:
    """Run the evaluation cases and check the ``eval:`` targets (T21, S12).

    Exit code 0: every target met; 3: minimum and security hold but some target is unmet or a
    documented known failure failed; 1: minimum/security broken or a NEW failure (regression);
    2: configuration, cases file, index/database or API error. See ``src/api/evaluation.py``.
    """
    from src.api.evaluation import EXIT_ERROR, EvalError, format_report, run_eval

    try:
        settings = load_settings()
    except ConfigError as exc:
        print(f"eval: {exc}", file=sys.stderr)
        return EXIT_ERROR
    configure_logging_from_settings(settings, console=False)
    cases = Path(args.cases) if args.cases else DEFAULT_EVAL_CASES
    out = Path(args.out) if args.out else DEFAULT_EVAL_OUT
    if args.api_url:
        print(
            "eval: warning: HTTP mode creates real tickets on the server "
            "(el modo HTTP crea tickets reales en el servidor)",
            file=sys.stderr,
        )
    try:
        report, summary = run_eval(settings, cases, out, args.api_url, args.api_key)
    except EvalError as exc:
        print(f"eval: {exc}", file=sys.stderr)
        return EXIT_ERROR
    print(f"eval: {len(report.results)} cases ({report.backend}) -> {_display(out)}")
    print(f"  summary -> {_display(summary)}")
    print(format_report(report))
    return report.exit_code


def cmd_mcp(args: argparse.Namespace) -> int:
    """Start the MCP server (T18, S10): stdio (no network) by default, HTTP behind the API key.

    On stdio stdout carries the protocol, so logs go to ``logs/`` and stderr only. Fails fast
    on invalid config, and the HTTP transport also without a valid ``DESKPILOT_API_KEY``.
    """
    from src.api import build_services
    from src.api.mcp_server import build_mcp_server, run_http, run_stdio
    from src.utils.config import require_api_key

    try:
        settings = load_settings()
        transport: str = args.transport or settings.mcp.transport
        if transport == "http":
            require_api_key(settings, "mcp")
    except ConfigError as exc:
        print(f"mcp: {exc}", file=sys.stderr)
        return EXIT_CONFIG_ERROR
    # Before building the server: the SDK only installs its own handler if none exists.
    configure_logging_from_settings(settings)
    host: str = args.host or settings.mcp.host
    port: int = args.port or settings.mcp.port
    services = build_services(settings)
    try:
        server = build_mcp_server(settings, services)
        if transport == "http":
            run_http(server, settings, host, port, settings.mcp.path)
        else:
            run_stdio(server)
    finally:
        services.close()
    return EXIT_OK


HANDLERS: dict[str, Callable[[argparse.Namespace], int]] = {
    "generate-data": cmd_generate_data,
    "load-db": cmd_load_db,
    "index": cmd_index,
    "serve": cmd_serve,
    "mcp": cmd_mcp,
    "export-openapi": cmd_export_openapi,
    "eval": cmd_eval,
}


def build_parser() -> argparse.ArgumentParser:
    """Build the CLI parser with one subparser per pipeline step."""
    parser = argparse.ArgumentParser(
        prog="deskpilot",
        description="DeskPilot AI: RAG-based L1 service desk assistant (synthetic data).",
    )
    subparsers = parser.add_subparsers(dest="command", required=True, metavar="COMMAND")
    for name, (help_text, _task) in SUBCOMMANDS.items():
        subparser = subparsers.add_parser(name, help=help_text, description=help_text)
        if name == "generate-data":
            subparser.add_argument(
                "--seed", type=_non_negative_int, help="random seed (default: data.seed)"
            )
            subparser.add_argument(
                "--n", type=_positive_int, help="number of tickets (default: data.n_tickets)"
            )
        elif name == "serve":
            subparser.add_argument("--host", help="bind address (default: api.host)")
            subparser.add_argument(
                "--port", type=_positive_int, help="TCP port (default: api.port)"
            )
        elif name == "mcp":
            subparser.add_argument(
                "--transport",
                choices=("stdio", "http"),
                help="stdio (default, no network) or streamable HTTP (needs the API key)",
            )
            subparser.add_argument("--host", help="HTTP bind address (default: mcp.host)")
            subparser.add_argument(
                "--port", type=_positive_int, help="HTTP port (default: mcp.port)"
            )
        elif name == "export-openapi":
            subparser.add_argument(
                "--host",
                help="public host of the API, without https:// (default: a placeholder)",
            )
            subparser.add_argument(
                "--out",
                help="output file (default: integrations/copilot_studio/openapi.json)",
            )
        elif name == "eval":
            subparser.add_argument("--cases", help="cases CSV (default: tests/eval/cases.csv)")
            subparser.add_argument(
                "--out",
                help="results CSV; the JSON summary goes next to it "
                "(default: tests/eval/results.csv)",
            )
            subparser.add_argument(
                "--api-url",
                help="evaluate a running API over HTTP instead of in-process services",
            )
            subparser.add_argument(
                "--api-key",
                help="X-API-Key for --api-url (default: DESKPILOT_API_KEY; prefer the env var)",
            )
        elif name == "load-db":
            subparser.add_argument(
                "--run-sql",
                action="store_true",
                help="after loading, run the 10 queries of integrations/fabric/sql and print them",
            )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Parse ``argv`` and dispatch the selected subcommand; return the process exit code."""
    args = build_parser().parse_args(argv)
    command: str = args.command
    handler = HANDLERS.get(command)
    if handler is not None:
        return handler(args)
    _help_text, task = SUBCOMMANDS[command]
    print(f"{command}: not implemented yet ({task})", file=sys.stderr)
    return EXIT_NOT_IMPLEMENTED


if __name__ == "__main__":
    sys.exit(main())
