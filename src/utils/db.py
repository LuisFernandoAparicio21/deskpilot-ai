"""SQLite helpers for local mode (S5, RF-18, RF-20).

- ``connect`` opens a database with ``sqlite3.Row`` rows, foreign keys on and explicit
  transactions (``isolation_level=None``: nothing is committed behind our back).
- ``sqlite_connection`` is a context manager that always closes the connection
  (``with sqlite3.connect(...)`` alone only ends the transaction, it does not close).
- ``transaction`` wraps a block in ``BEGIN`` / ``COMMIT`` and rolls back on any error.
  SQLite supports transactional DDL, so ``DROP``/``CREATE`` are rolled back too.
- ``run_sql_file`` executes one ``.sql`` file (a single statement) and returns its
  columns and rows; ``format_table`` renders them as a plain-text table for the CLI.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

from src.utils.config import PROJECT_ROOT

SQL_DIR = PROJECT_ROOT / "integrations" / "fabric" / "sql"
QUERY_GLOB = "[0-9][0-9]_*.sql"  # numbered business queries; DDL files are excluded

SqlValue = str | int | float | bytes | None


@dataclass(frozen=True)
class QueryResult:
    """Columns and rows returned by one SQL file."""

    name: str
    columns: tuple[str, ...]
    rows: tuple[tuple[SqlValue, ...], ...]


def connect(db_path: Path) -> sqlite3.Connection:
    """Open ``db_path`` (creating its folder) with Row factory and foreign keys enabled."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path, isolation_level=None)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


@contextmanager
def sqlite_connection(db_path: Path) -> Iterator[sqlite3.Connection]:
    """Yield a connection from ``connect`` and close it when the block ends."""
    conn = connect(db_path)
    try:
        yield conn
    finally:
        conn.close()


@contextmanager
def transaction(conn: sqlite3.Connection) -> Iterator[sqlite3.Connection]:
    """Run the block inside ``BEGIN``/``COMMIT``; ``ROLLBACK`` if it raises."""
    conn.execute("BEGIN")
    try:
        yield conn
    except BaseException:
        conn.execute("ROLLBACK")
        raise
    conn.execute("COMMIT")


def list_query_files(sql_dir: Path = SQL_DIR) -> list[Path]:
    """Numbered query files (``01_*.sql`` .. ``10_*.sql``) sorted by name."""
    return sorted(sql_dir.glob(QUERY_GLOB))


def run_sql_file(conn: sqlite3.Connection, path: Path) -> QueryResult:
    """Execute the single statement in ``path`` and return its columns and rows."""
    sql = path.read_text(encoding="utf-8")
    cursor = conn.execute(sql)
    columns = tuple(str(col[0]) for col in cursor.description or ())
    rows = tuple(tuple(row) for row in cursor.fetchall())
    return QueryResult(name=path.stem, columns=columns, rows=rows)


def _cell(value: SqlValue) -> str:
    if value is None:
        return ""
    if isinstance(value, float):
        return f"{value:.2f}"
    return str(value)


def format_table(
    columns: Sequence[str], rows: Sequence[Sequence[SqlValue]], max_rows: int | None = None
) -> str:
    """Render ``rows`` as an aligned text table; cap at ``max_rows`` with a note."""
    shown = list(rows if max_rows is None else rows[:max_rows])
    cells = [[_cell(v) for v in row] for row in shown]
    widths = [max([len(col), *(len(row[i]) for row in cells)]) for i, col in enumerate(columns)]
    lines = [
        "  ".join(col.ljust(w) for col, w in zip(columns, widths, strict=True)),
        "  ".join("-" * w for w in widths),
    ]
    lines += ["  ".join(c.ljust(w) for c, w in zip(row, widths, strict=True)) for row in cells]
    hidden = len(rows) - len(shown)
    if hidden > 0:
        lines.append(f"... ({hidden} more rows)")
    return "\n".join(line.rstrip() for line in lines)
