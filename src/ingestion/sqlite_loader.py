"""Load the synthetic CSV files into the local SQLite database (S5, RF-18, RF-20).

``load_sqlite`` reads ``<raw>/tickets.csv`` and ``<raw>/sucursales.csv`` (written by
``python main.py generate-data``), validates every row with the generator's Pydantic
models and, inside ONE transaction, drops and recreates three tables with explicit DDL:

- ``sucursales``: branch dimension (PK ``sucursal``), used by the JOIN queries.
- ``tickets``: the 17 fields of requirements section 11 (PK ``ticket_id``, FK to
  ``sucursales``) plus indexes on the columns the 10 SQL queries group or filter by.
- ``tickets_nuevos``: empty table for tickets created by ``crear_ticket`` (T17). It has
  the same 17 columns plus ``descripcion``; the fields only known after resolution
  (``fecha_cierre``, ``sla_cumplido``, ``horas_resolucion``, ``solucion``) are nullable.
  The Fabric Warehouse DDL (T11) must mirror this column list (``TICKETS_NUEVOS_COLUMNS``).

Flags (``sla_cumplido``, ``es_repetitivo``, ``es_foranea``) are stored as INTEGER 0/1
(``NULL`` for open tickets) so ``SUM(flag)`` works the same in SQLite and T-SQL. Dates are
TEXT ``YYYY-MM-DD HH:MM:SS``. Running the load twice gives the same database: it is a
full reset of local mode, including ``tickets_nuevos``. If anything fails, the
transaction is rolled back and the previous tables stay untouched.
"""

from __future__ import annotations

import csv
import logging
import sqlite3
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

from src.ingestion.ticket_generator import (
    DATE_FORMAT,
    SUCURSAL_FIELDS,
    TICKET_FIELDS,
    Sucursal,
    Ticket,
)
from src.utils.db import SqlValue, sqlite_connection, transaction

logger = logging.getLogger(__name__)

TICKETS_CSV = "tickets.csv"
SUCURSALES_CSV = "sucursales.csv"
TICKETS_NUEVOS_COLUMNS: tuple[str, ...] = (*TICKET_FIELDS, "descripcion")

_TICKET_COLUMNS_DDL = """
    ticket_id        TEXT    NOT NULL PRIMARY KEY,
    fecha_apertura   TEXT    NOT NULL,
    fecha_cierre     TEXT,
    categoria        TEXT    NOT NULL,
    subcategoria     TEXT    NOT NULL,
    prioridad        TEXT    NOT NULL CHECK (prioridad IN ('P1', 'P2', 'P3', 'P4')),
    sucursal         TEXT    NOT NULL{sucursal_fk},
    area             TEXT    NOT NULL,
    canal            TEXT    NOT NULL,
    sla_horas        INTEGER NOT NULL CHECK (sla_horas > 0),
    sla_cumplido     INTEGER CHECK (sla_cumplido IN (0, 1)),
    horas_resolucion REAL    CHECK (horas_resolucion >= 0),
    anio_mes         TEXT    NOT NULL,
    solucion         TEXT{solucion_null},
    es_repetitivo    INTEGER NOT NULL CHECK (es_repetitivo IN (0, 1)),
    idioma           TEXT    NOT NULL CHECK (idioma IN ('es', 'en')),
    estado           TEXT    NOT NULL
                     CHECK (estado IN ('abierto', 'en_proceso', 'resuelto', 'cerrado'))"""

DDL: tuple[str, ...] = (
    "DROP TABLE IF EXISTS tickets_nuevos",
    "DROP TABLE IF EXISTS tickets",
    "DROP TABLE IF EXISTS sucursales",
    """CREATE TABLE sucursales (
    sucursal   TEXT    NOT NULL PRIMARY KEY,
    ciudad     TEXT    NOT NULL,
    estado_mx  TEXT    NOT NULL,
    region     TEXT    NOT NULL,
    es_foranea INTEGER NOT NULL CHECK (es_foranea IN (0, 1))
)""",
    "CREATE TABLE tickets ("
    + _TICKET_COLUMNS_DDL.format(
        sucursal_fk=" REFERENCES sucursales (sucursal)", solucion_null=" NOT NULL"
    )
    + "\n)",
    "CREATE TABLE tickets_nuevos ("
    + _TICKET_COLUMNS_DDL.format(sucursal_fk="", solucion_null="")
    + ",\n    descripcion      TEXT    NOT NULL\n)",
    "CREATE INDEX ix_tickets_subcategoria ON tickets (subcategoria)",
    "CREATE INDEX ix_tickets_sucursal ON tickets (sucursal)",
    "CREATE INDEX ix_tickets_area ON tickets (area)",
    "CREATE INDEX ix_tickets_anio_mes ON tickets (anio_mes)",
    "CREATE INDEX ix_tickets_estado_prioridad ON tickets (estado, prioridad)",
)


class MissingDataError(FileNotFoundError):
    """A CSV produced by ``generate-data`` is missing."""


@dataclass(frozen=True)
class LoadResult:
    """Outcome of one ``load_sqlite`` run."""

    db_path: Path
    n_tickets: int
    n_sucursales: int


def _require_csv(path: Path) -> None:
    if not path.is_file():
        raise MissingDataError(
            f"{path} not found: run `python main.py generate-data` first "
            "(corre primero generate-data)."
        )


def _read_csv(path: Path, expected: tuple[str, ...]) -> Iterator[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if tuple(reader.fieldnames or ()) != expected:
            raise ValueError(
                f"{path.name} has columns {reader.fieldnames}, expected {list(expected)}"
            )
        yield from reader


def _flag(value: bool | None) -> int | None:
    return None if value is None else int(value)


def sucursal_values(row: dict[str, str]) -> tuple[SqlValue, ...]:
    """Validate one ``sucursales.csv`` row and return it in ``SUCURSAL_FIELDS`` order."""
    s = Sucursal.model_validate(row)
    return (s.sucursal, s.ciudad, s.estado_mx, s.region, int(s.es_foranea))


def ticket_values(row: dict[str, str]) -> tuple[SqlValue, ...]:
    """Validate one ``tickets.csv`` row (empty cell = NULL) in ``TICKET_FIELDS`` order."""
    t = Ticket.model_validate({key: (value if value != "" else None) for key, value in row.items()})
    return (
        t.ticket_id,
        t.fecha_apertura.strftime(DATE_FORMAT),
        t.fecha_cierre.strftime(DATE_FORMAT) if t.fecha_cierre else None,
        t.categoria,
        t.subcategoria,
        t.prioridad,
        t.sucursal,
        t.area,
        t.canal,
        t.sla_horas,
        _flag(t.sla_cumplido),
        t.horas_resolucion,
        t.anio_mes,
        t.solucion,
        int(t.es_repetitivo),
        t.idioma,
        t.estado,
    )


def _insert(table: str, columns: tuple[str, ...]) -> str:
    placeholders = ", ".join("?" for _ in columns)
    return f"INSERT INTO {table} ({', '.join(columns)}) VALUES ({placeholders})"


def create_schema(conn: sqlite3.Connection) -> None:
    """Drop and recreate the three tables and their indexes (call inside a transaction)."""
    for statement in DDL:
        conn.execute(statement)


def load_sqlite(raw_dir: Path, db_path: Path) -> LoadResult:
    """Recreate ``sucursales``, ``tickets`` and ``tickets_nuevos`` from the CSV files."""
    sucursales_csv, tickets_csv = raw_dir / SUCURSALES_CSV, raw_dir / TICKETS_CSV
    for path in (sucursales_csv, tickets_csv):  # fail before touching the database
        _require_csv(path)
    sucursales = [sucursal_values(r) for r in _read_csv(sucursales_csv, SUCURSAL_FIELDS)]
    tickets = [ticket_values(r) for r in _read_csv(tickets_csv, TICKET_FIELDS)]
    with sqlite_connection(db_path) as conn, transaction(conn):
        create_schema(conn)
        conn.executemany(_insert("sucursales", SUCURSAL_FIELDS), sucursales)
        conn.executemany(_insert("tickets", TICKET_FIELDS), tickets)
    result = LoadResult(db_path=db_path, n_tickets=len(tickets), n_sucursales=len(sucursales))
    logger.info(
        "sqlite database loaded",
        extra={"n_tickets": result.n_tickets, "n_sucursales": result.n_sucursales},
    )
    return result
