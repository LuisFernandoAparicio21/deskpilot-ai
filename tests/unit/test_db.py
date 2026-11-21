"""Unit tests for src/utils/db.py (SQLite helpers)."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from src.utils.db import (
    QueryResult,
    connect,
    format_table,
    list_query_files,
    run_sql_file,
    sqlite_connection,
    transaction,
)


def _make_table(conn: sqlite3.Connection) -> None:
    conn.execute("CREATE TABLE t (id INTEGER PRIMARY KEY, name TEXT NOT NULL)")


def test_connect_creates_folder_and_sets_row_factory(tmp_path: Path) -> None:
    db = tmp_path / "nested" / "local.db"
    conn = connect(db)
    try:
        assert db.parent.is_dir()
        assert conn.row_factory is sqlite3.Row
        assert conn.execute("PRAGMA foreign_keys").fetchone()[0] == 1
        assert conn.isolation_level is None
    finally:
        conn.close()


def test_sqlite_connection_closes_on_exit(tmp_path: Path) -> None:
    with sqlite_connection(tmp_path / "a.db") as conn:
        assert conn.execute("SELECT 1").fetchone()[0] == 1
    with pytest.raises(sqlite3.ProgrammingError):
        conn.execute("SELECT 1")


def test_transaction_commits(tmp_path: Path) -> None:
    db = tmp_path / "a.db"
    with sqlite_connection(db) as conn, transaction(conn):
        _make_table(conn)
        conn.execute("INSERT INTO t (name) VALUES ('x')")
    with sqlite_connection(db) as conn:
        assert conn.execute("SELECT COUNT(*) FROM t").fetchone()[0] == 1


def test_transaction_rolls_back_ddl_and_dml_on_error(tmp_path: Path) -> None:
    db = tmp_path / "a.db"
    with sqlite_connection(db) as conn:
        with pytest.raises(RuntimeError), transaction(conn):
            _make_table(conn)
            conn.execute("INSERT INTO t (name) VALUES ('x')")
            raise RuntimeError("boom")
        tables = conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'").fetchall()
        assert tables == []


def test_run_sql_file_returns_columns_and_rows(tmp_path: Path) -> None:
    sql = tmp_path / "01_demo.sql"
    sql.write_text(
        "-- comment with ñ\nSELECT name, COUNT(*) AS n FROM t GROUP BY name ORDER BY name;\n",
        encoding="utf-8",
    )
    with sqlite_connection(tmp_path / "a.db") as conn:
        _make_table(conn)
        conn.executemany("INSERT INTO t (name) VALUES (?)", [("b",), ("a",), ("b",)])
        result = run_sql_file(conn, sql)
    assert result == QueryResult(name="01_demo", columns=("name", "n"), rows=(("a", 1), ("b", 2)))


def test_list_query_files_only_numbered_and_sorted(tmp_path: Path) -> None:
    for name in ("02_b.sql", "01_a.sql", "ddl_tickets_nuevos.sql", "notes.txt"):
        (tmp_path / name).write_text("SELECT 1", encoding="utf-8")
    assert [p.name for p in list_query_files(tmp_path)] == ["01_a.sql", "02_b.sql"]


def test_format_table_aligns_and_formats_values() -> None:
    text = format_table(("area", "pct", "n"), [("Caja", 85.456, 3), ("Crédito", None, 12)])
    lines = text.splitlines()
    assert lines[0].split() == ["area", "pct", "n"]
    assert set(lines[1].replace(" ", "")) == {"-"}
    assert lines[2].split() == ["Caja", "85.46", "3"]
    assert lines[3].split() == ["Crédito", "12"]
    assert all(line == line.rstrip() for line in lines)


def test_format_table_caps_rows() -> None:
    text = format_table(("n",), [(i,) for i in range(5)], max_rows=2)
    assert text.splitlines()[-1] == "... (3 more rows)"
    assert len(text.splitlines()) == 5
