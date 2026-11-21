"""Static checks of the Fabric Warehouse DDL for dbo.tickets_nuevos (S6, RF-18).

The DDL must mirror ``TICKETS_NUEVOS_COLUMNS`` of the SQLite loader (same columns,
same order, same nullability) and use only types that Fabric Warehouse supports.
"""

from __future__ import annotations

import re
import sqlite3

import sqlglot
from sqlglot import exp
from sqlglot.errors import ErrorLevel

from src.ingestion.sqlite_loader import TICKETS_NUEVOS_COLUMNS, create_schema
from src.utils.db import SQL_DIR, list_query_files

DDL_PATH = SQL_DIR / "warehouse_ddl.sql"
# Supported table types in Fabric Warehouse (docs/sources.md, "Data types in Fabric...").
ALLOWED_TYPES = {
    exp.DataType.Type.VARCHAR,
    exp.DataType.Type.CHAR,
    exp.DataType.Type.DATETIME2,
    exp.DataType.Type.INT,
    exp.DataType.Type.FLOAT,
}


def _statements() -> list[exp.Expr]:
    sql = DDL_PATH.read_text(encoding="utf-8")
    parsed = sqlglot.parse(sql, read="tsql", error_level=ErrorLevel.RAISE)
    return [s for s in parsed if s is not None]


def _create() -> exp.Create:
    create = _statements()[0]
    assert isinstance(create, exp.Create)
    return create


def _columns() -> list[exp.ColumnDef]:
    return list(_create().find_all(exp.ColumnDef))


def _sqlite_not_null() -> dict[str, bool]:
    conn = sqlite3.connect(":memory:")
    try:
        create_schema(conn)
        rows = conn.execute("PRAGMA table_info(tickets_nuevos)").fetchall()
    finally:
        conn.close()
    return {str(row[1]): bool(row[3]) for row in rows}


def test_ddl_is_not_one_of_the_numbered_queries() -> None:
    assert DDL_PATH.is_file()
    assert DDL_PATH not in list_query_files(SQL_DIR)


def test_ddl_starts_with_explanatory_comment() -> None:
    sql = DDL_PATH.read_text(encoding="utf-8")
    assert sql.startswith("--")
    for label in ("Warehouse", "tickets_nuevos", "NOT ENFORCED", "datetime2"):
        assert label in sql


def test_ddl_parses_as_tsql_create_and_alter() -> None:
    statements = _statements()
    assert len(statements) == 2
    table = _create().find(exp.Table)
    assert table is not None
    assert (table.db, table.name) == ("dbo", "tickets_nuevos")
    alter = " ".join(statements[1].sql("tsql").split())  # sqlglot keeps it as a Command
    assert re.search(
        r"ALTER TABLE dbo\.tickets_nuevos ADD CONSTRAINT \w+ "
        r"PRIMARY KEY NONCLUSTERED \(ticket_id\) NOT ENFORCED",
        alter,
    ), alter


def test_columns_match_sqlite_loader() -> None:
    assert tuple(c.name for c in _columns()) == TICKETS_NUEVOS_COLUMNS


def test_nullability_matches_sqlite_loader() -> None:
    expected = _sqlite_not_null()
    for column in _columns():
        not_null = any(
            isinstance(c.kind, exp.NotNullColumnConstraint) and not c.kind.args.get("allow_null")
            for c in column.constraints
        )
        assert not_null is expected[column.name], column.name


def test_only_fabric_supported_types() -> None:
    for column in _columns():
        kind = column.args["kind"]
        assert kind.this in ALLOWED_TYPES, f"{column.name}: {kind.sql('tsql')}"
        if kind.this is exp.DataType.Type.DATETIME2:
            (precision,) = kind.expressions  # Fabric requires an explicit precision
            assert 0 <= int(precision.name) <= 6
        if kind.this in {exp.DataType.Type.VARCHAR, exp.DataType.Type.CHAR}:
            (size,) = kind.expressions
            assert 1 <= int(size.name) <= 8000


def test_no_unsupported_constructs() -> None:
    sql = re.sub(r"--[^\n]*", "", DDL_PATH.read_text(encoding="utf-8")).upper()
    for forbidden in ("NVARCHAR", "NCHAR", "DATETIME ", "CHECK", "DEFAULT", "IDENTITY", " BIT"):
        assert forbidden not in sql, forbidden
