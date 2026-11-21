"""Command-line entry point for DeskPilot AI.

Every pipeline step runs through a subcommand:

    python main.py generate-data | load-db | index | serve | eval | export-openapi

Subcommands without a handler yet only report which task will implement them and exit
with code 2. Implemented so far: ``generate-data`` (T9) and ``load-db`` (T10).
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Callable, Sequence
from pathlib import Path

from src.ingestion.sqlite_loader import MissingDataError, load_sqlite
from src.ingestion.ticket_generator import generate_dataset
from src.utils.config import PROJECT_ROOT, ConfigError, load_settings
from src.utils.db import SQL_DIR, format_table, list_query_files, run_sql_file, sqlite_connection
from src.utils.logging import configure_logging_from_settings

EXIT_OK = 0
EXIT_CONFIG_ERROR = 1
EXIT_NOT_IMPLEMENTED = 2
EXIT_DATA_ERROR = 3

SQL_SUMMARY_MAX_ROWS = 10  # rows printed per query by ``load-db --run-sql``

# Subcommand -> (help text, task that implements it).
SUBCOMMANDS: dict[str, tuple[str, str]] = {
    "generate-data": ("Generate the synthetic ticket dataset (seeded).", "T9"),
    "load-db": ("Load the generated tickets into the local SQLite database.", "T10"),
    "index": ("Chunk, embed and index the knowledge base into the vector database.", "T14"),
    "serve": ("Start the FastAPI service.", "T16"),
    "eval": ("Run the agent evaluation cases and save the results.", "T21"),
    "export-openapi": ("Export the OpenAPI spec for Copilot Studio.", "T19"),
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


HANDLERS: dict[str, Callable[[argparse.Namespace], int]] = {
    "generate-data": cmd_generate_data,
    "load-db": cmd_load_db,
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
