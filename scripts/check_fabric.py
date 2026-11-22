"""Check the Microsoft Fabric connection step by step (S6, S16, T25/T30).

Run from the repo root::

    .venv\\Scripts\\python -m scripts.check_fabric [--write-test] [--timeout 30]

Checks, in order (it stops at the first blocking failure):

1. the FABRIC_* / AZURE_* variables are present (names only; values are never printed);
2. ODBC Driver 18 for SQL Server is installed;
3. a Microsoft Entra token can be obtained;
4. SQL analytics endpoint: ``SELECT COUNT(*) FROM dbo.tickets``;
5. Warehouse: ``dbo.tickets_nuevos`` exists;
6. only with ``--write-test``: insert one test ticket in ``dbo.tickets_nuevos`` and
   delete it again.

Exit codes: 0 = every check passed; 1 = a check failed; 2 = bad configuration or usage
(missing or invalid variables, config.yaml problems), nothing was contacted.

Connection logic lives in ``src.utils.fabric`` and the INSERT in ``src.api.repository``;
this script only orchestrates and reports. Errors are printed without tracebacks.
Steps to prepare Fabric: docs/MANUAL_STEPS.md.
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from datetime import datetime
from typing import Any

from dotenv import dotenv_values

from scripts import use_utf8_console
from src.api.repository import NewTicket, build_fabric_repository
from src.utils.config import (
    DEFAULT_CONFIG_PATH,
    DEFAULT_ENV_FILE,
    ConfigError,
    FabricConfig,
    _read_yaml,
    load_settings,
)
from src.utils.fabric import (
    ODBC_DRIVER,
    FabricAuthError,
    FabricConnectionError,
    FabricConnectionFactory,
    FabricDriverError,
)

EXIT_OK = 0
EXIT_CHECK_FAILED = 1
EXIT_CONFIG = 2

MANUAL = "docs/MANUAL_STEPS.md"
TEST_TICKET_TEXT = "check_fabric.py connectivity test; safe to delete"


def ok(message: str) -> None:
    print(f"✓ {message}")


def fail(message: str, hint: str) -> None:
    print(f"✗ {message}")
    print(f"  Qué hacer: {hint}")


_SQLSTATE_RE = re.compile(r"[0-9A-Z]{5}")


def describe(exc: Exception) -> str:
    """Safe one-line description: our own messages carry no secrets; others, type only."""
    if isinstance(exc, FabricDriverError | FabricAuthError | FabricConnectionError | ConfigError):
        return str(exc)
    sqlstate = exc.args[0] if exc.args and isinstance(exc.args[0], str) else ""
    if _SQLSTATE_RE.fullmatch(sqlstate) and type(exc).__module__.split(".")[0] == "pyodbc":
        return f"{type(exc).__name__} (SQLSTATE {sqlstate})"
    return type(exc).__name__  # never the raw message: it may hold a connection string/token


@contextmanager
def _fabric_mode() -> Iterator[None]:
    """Load settings in fabric mode without leaving DESKPILOT_MODE changed afterwards.

    ``load_settings`` reads the mode only from the environment, so it is set for the
    duration of the block and the previous value is always restored.
    """
    previous = os.environ.get("DESKPILOT_MODE")
    os.environ["DESKPILOT_MODE"] = "fabric"
    try:
        yield
    finally:
        if previous is None:
            os.environ.pop("DESKPILOT_MODE", None)
        else:
            os.environ["DESKPILOT_MODE"] = previous


def fabric_variable_names() -> dict[str, str]:
    """Environment variable names from config.yaml (``fabric`` section), by field."""
    section = _read_yaml(DEFAULT_CONFIG_PATH).get("fabric")
    config = FabricConfig.model_validate(section)
    return {field.removesuffix("_env"): name for field, name in config.model_dump().items()}


def check_variables() -> bool:
    """Step 1: report which variables are present; never print values."""
    names = fabric_variable_names()
    values: dict[str, Any] = {}
    if DEFAULT_ENV_FILE.is_file():
        values.update(dotenv_values(DEFAULT_ENV_FILE))
    values.update(os.environ)
    required = ("sql_endpoint", "lakehouse_database", "warehouse_endpoint", "warehouse_database")
    sp = ("tenant_id", "client_id", "client_secret")
    missing = [names[k] for k in required if not values.get(names[k])]
    sp_present = [names[k] for k in sp if values.get(names[k])]
    sp_missing = [names[k] for k in sp if not values.get(names[k])]
    for key in required:
        present = bool(values.get(names[key]))
        print(f"  {'✓' if present else '✗'} {names[key]}: {'set' if present else 'MISSING'}")
    for key in sp:
        present = bool(values.get(names[key]))
        print(f"  {'✓' if present else '-'} {names[key]}: {'set' if present else 'not set'}")
    if sp_present and sp_missing:
        missing += sp_missing
    if missing:
        fail(
            f"Missing variables: {', '.join(missing)}",
            f"copy .env.example to .env and fill them (see {MANUAL}, Fabric section). The "
            "service principal variables go together: all three, or none to use `az login`.",
        )
        return False
    mode = "service principal" if len(sp_present) == len(sp) else "DefaultAzureCredential"
    ok(f"Variables present (authentication: {mode})")
    return True


def check_driver() -> bool:
    try:
        import pyodbc
    except ImportError:
        fail("pyodbc is not importable", "run: .venv\\Scripts\\pip install -r requirements.txt")
        return False
    drivers = pyodbc.drivers()
    if ODBC_DRIVER not in drivers:
        fail(
            f"{ODBC_DRIVER} not installed (found: {', '.join(drivers) or 'none'})",
            "install Microsoft ODBC Driver 18 for SQL Server "
            f"(https://aka.ms/downloadmsodbcsql); see {MANUAL}.",
        )
        return False
    ok(f"{ODBC_DRIVER} installed")
    return True


def check_token(factory: FabricConnectionFactory) -> bool:
    try:
        factory._token_struct()
    except FabricAuthError as exc:
        fail(describe(exc), f"verify the AZURE_* values or run `az login`; see {MANUAL}.")
        return False
    ok(f"Microsoft Entra token obtained ({factory.auth_mode})")
    return True


def _scalar(factory: FabricConnectionFactory, target: str, sql: str) -> Any:
    conn = factory.connect_lakehouse() if target == "lakehouse" else factory.connect_warehouse()
    try:
        cursor = conn.cursor()
        cursor.execute(sql)
        return cursor.fetchone()[0]
    finally:
        conn.close()


def check_lakehouse(factory: FabricConnectionFactory) -> bool:
    try:
        count = _scalar(factory, "lakehouse", "SELECT COUNT(*) FROM dbo.tickets")
    except Exception as exc:
        fail(
            f"SQL analytics endpoint / dbo.tickets: {describe(exc)}",
            "check FABRIC_SQL_ENDPOINT and FABRIC_LAKEHOUSE_DATABASE, that the notebook "
            f"created the Delta table `tickets`, and your workspace role; see {MANUAL}.",
        )
        return False
    ok(f"SQL analytics endpoint reachable; dbo.tickets has {count} rows")
    return True


def check_warehouse(factory: FabricConnectionFactory) -> bool:
    try:
        count = _scalar(factory, "warehouse", "SELECT COUNT(*) FROM dbo.tickets_nuevos")
    except Exception as exc:
        fail(
            f"Warehouse / dbo.tickets_nuevos: {describe(exc)}",
            "check FABRIC_WAREHOUSE_ENDPOINT / FABRIC_WAREHOUSE_DATABASE and run "
            f"integrations/fabric/sql/warehouse_ddl.sql in the Warehouse; see {MANUAL}.",
        )
        return False
    ok(f"Warehouse reachable; dbo.tickets_nuevos exists ({count} rows)")
    return True


def check_write(factory: FabricConnectionFactory) -> bool:
    """Insert one test ticket through the real repository and delete it."""
    repository = build_fabric_repository(factory)
    ticket = NewTicket(
        fecha_apertura=datetime.now().replace(microsecond=0),
        categoria="Prueba",
        subcategoria="check_fabric",
        prioridad="P4",
        sucursal="Prueba",
        area="Prueba",
        canal="script",
        sla_horas=72,
        idioma="es",
        descripcion=TEST_TICKET_TEXT,
    )
    try:
        ticket_id = repository.create_ticket(ticket)
    except Exception as exc:
        fail(
            f"Insert into dbo.tickets_nuevos: {describe(exc)}",
            f"your identity needs write permission on the Warehouse; see {MANUAL}.",
        )
        return False
    ok(f"Test ticket {ticket_id} inserted into dbo.tickets_nuevos")
    try:
        conn = factory.connect_warehouse()
        try:
            sql = "DELETE FROM dbo.tickets_nuevos WHERE ticket_id = ?"
            conn.cursor().execute(sql, (ticket_id,))
            conn.commit()
        finally:
            conn.close()
    except Exception as exc:
        fail(
            f"Could not delete test ticket {ticket_id}: {describe(exc)}",
            f"delete it by hand: DELETE FROM dbo.tickets_nuevos WHERE ticket_id = '{ticket_id}'",
        )
        return False
    ok(f"Test ticket {ticket_id} deleted")
    return True


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Check the Fabric connection (read-only unless --write-test).",
        epilog="Exit codes: 0 all passed, 1 a check failed, 2 bad configuration or usage.",
    )
    parser.add_argument(
        "--write-test",
        action="store_true",
        help="also insert and delete one test ticket in dbo.tickets_nuevos",
    )
    parser.add_argument("--timeout", type=int, default=30, help="connection timeout in seconds")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    print("Fabric connection check")
    try:
        if not check_variables():
            return EXIT_CONFIG
        with _fabric_mode():  # this script always targets fabric
            settings = load_settings()
        factory = FabricConnectionFactory.from_settings(settings, timeout_s=args.timeout)
    except ConfigError as exc:
        fail(describe(exc), f"fix .env / config.yaml; see {MANUAL}.")
        return EXIT_CONFIG
    if not (check_driver() and check_token(factory)):
        return EXIT_CHECK_FAILED
    lakehouse_ok = check_lakehouse(factory)
    warehouse_ok = check_warehouse(factory)
    write_ok = True
    if args.write_test and warehouse_ok:
        write_ok = check_write(factory)
    elif not args.write_test:
        print("- write test skipped (use --write-test to insert and delete a test ticket)")
    passed = lakehouse_ok and warehouse_ok and write_ok
    print("Result: " + ("all checks passed" if passed else "FAILED, see the ✗ lines above"))
    return EXIT_OK if passed else EXIT_CHECK_FAILED


if __name__ == "__main__":
    use_utf8_console()
    sys.exit(main())
