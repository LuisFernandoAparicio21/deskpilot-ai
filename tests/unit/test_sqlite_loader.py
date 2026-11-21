"""Unit tests for src/ingestion/sqlite_loader.py."""

from __future__ import annotations

import csv
import sqlite3
from pathlib import Path

import pytest

from src.ingestion.sqlite_loader import (
    TICKETS_NUEVOS_COLUMNS,
    MissingDataError,
    load_sqlite,
    ticket_values,
)
from src.ingestion.ticket_generator import TICKET_FIELDS, generate_dataset
from src.utils.db import sqlite_connection

SLA = {"P1": 4, "P2": 8, "P3": 24, "P4": 72}


@pytest.fixture(scope="module")
def raw_dir(tmp_path_factory: pytest.TempPathFactory) -> Path:
    base = tmp_path_factory.mktemp("data")
    generate_dataset(11, 400, base / "raw", base / "sample", SLA)
    return base / "raw"


def _columns(conn: sqlite3.Connection, table: str) -> list[str]:
    return [row["name"] for row in conn.execute(f"PRAGMA table_info({table})")]


def test_load_creates_three_tables_with_all_rows(raw_dir: Path, tmp_path: Path) -> None:
    db = tmp_path / "local.db"
    result = load_sqlite(raw_dir, db)
    assert (result.db_path, result.n_tickets, result.n_sucursales) == (db, 400, 120)
    with sqlite_connection(db) as conn:
        assert conn.execute("SELECT COUNT(*) FROM tickets").fetchone()[0] == 400
        assert conn.execute("SELECT COUNT(*) FROM sucursales").fetchone()[0] == 120
        assert conn.execute("SELECT COUNT(*) FROM tickets_nuevos").fetchone()[0] == 0
        assert _columns(conn, "tickets") == list(TICKET_FIELDS)
        assert _columns(conn, "tickets_nuevos") == list(TICKETS_NUEVOS_COLUMNS)
        assert conn.execute("PRAGMA foreign_key_check").fetchall() == []


def test_schema_has_primary_keys_and_indexes(raw_dir: Path, tmp_path: Path) -> None:
    db = tmp_path / "local.db"
    load_sqlite(raw_dir, db)
    with sqlite_connection(db) as conn:
        pk = {
            table: [r["name"] for r in conn.execute(f"PRAGMA table_info({table})") if r["pk"]]
            for table in ("tickets", "sucursales", "tickets_nuevos")
        }
        indexes = {r["name"] for r in conn.execute("PRAGMA index_list(tickets)")}
    assert pk == {
        "tickets": ["ticket_id"],
        "sucursales": ["sucursal"],
        "tickets_nuevos": ["ticket_id"],
    }
    assert {"ix_tickets_subcategoria", "ix_tickets_sucursal", "ix_tickets_anio_mes"} <= indexes


def test_flags_are_integers_and_open_tickets_are_null(raw_dir: Path, tmp_path: Path) -> None:
    db = tmp_path / "local.db"
    load_sqlite(raw_dir, db)
    with sqlite_connection(db) as conn:
        flags = conn.execute(
            "SELECT DISTINCT typeof(sla_cumplido), typeof(es_repetitivo) FROM tickets"
            " WHERE estado IN ('resuelto', 'cerrado')"
        ).fetchall()
        open_rows = conn.execute(
            "SELECT fecha_cierre, sla_cumplido, horas_resolucion FROM tickets"
            " WHERE estado IN ('abierto', 'en_proceso')"
        ).fetchall()
        foranea = conn.execute("SELECT DISTINCT es_foranea FROM sucursales").fetchall()
    assert [tuple(r) for r in flags] == [("integer", "integer")]
    assert all(tuple(r) == (None, None, None) for r in open_rows)
    assert sorted(r[0] for r in foranea) == [0, 1]


def test_load_is_idempotent(raw_dir: Path, tmp_path: Path) -> None:
    db = tmp_path / "local.db"
    load_sqlite(raw_dir, db)
    with sqlite_connection(db) as conn:
        conn.execute(
            "INSERT INTO tickets_nuevos (ticket_id, fecha_apertura, categoria, subcategoria,"
            " prioridad, sucursal, area, canal, sla_horas, anio_mes, es_repetitivo, idioma,"
            " estado, descripcion) VALUES ('NEW-1', '2026-11-01 09:00:00', 'Accesos', 'VPN',"
            " 'P3', 'Puebla 01', 'Caja', 'portal', 24, '2026-11', 1, 'es', 'abierto', 'x')"
        )
    first = load_sqlite(raw_dir, db)
    second = load_sqlite(raw_dir, db)
    assert first == second
    with sqlite_connection(db) as conn:
        assert conn.execute("SELECT COUNT(*) FROM tickets").fetchone()[0] == 400
        assert conn.execute("SELECT COUNT(*) FROM tickets_nuevos").fetchone()[0] == 0


@pytest.mark.parametrize("missing", ["tickets.csv", "sucursales.csv"])
def test_missing_csv_has_clear_message(raw_dir: Path, tmp_path: Path, missing: str) -> None:
    partial = tmp_path / "raw"
    partial.mkdir()
    for name in ("tickets.csv", "sucursales.csv"):
        if name != missing:
            (partial / name).write_bytes((raw_dir / name).read_bytes())
    db = tmp_path / "local.db"
    with pytest.raises(MissingDataError, match="generate-data"):
        load_sqlite(partial, db)
    assert not db.exists()


def test_failed_load_keeps_previous_tables(raw_dir: Path, tmp_path: Path) -> None:
    db = tmp_path / "local.db"
    load_sqlite(raw_dir, db)
    broken = tmp_path / "broken"
    broken.mkdir()
    (broken / "sucursales.csv").write_bytes((raw_dir / "sucursales.csv").read_bytes())
    with (raw_dir / "tickets.csv").open(encoding="utf-8", newline="") as handle:
        rows = list(csv.reader(handle))
    rows[1][6] = "Sucursal inexistente"  # violates the FK to sucursales
    with (broken / "tickets.csv").open("w", encoding="utf-8", newline="") as handle:
        csv.writer(handle, lineterminator="\n").writerows(rows)
    with pytest.raises(sqlite3.IntegrityError):
        load_sqlite(broken, db)
    with sqlite_connection(db) as conn:
        assert conn.execute("SELECT COUNT(*) FROM tickets").fetchone()[0] == 400


def test_wrong_header_is_rejected(raw_dir: Path, tmp_path: Path) -> None:
    bad = tmp_path / "raw"
    bad.mkdir()
    (bad / "sucursales.csv").write_bytes((raw_dir / "sucursales.csv").read_bytes())
    (bad / "tickets.csv").write_text("ticket_id,otra\nTCK-1,x\n", encoding="utf-8")
    with pytest.raises(ValueError, match="expected"):
        load_sqlite(bad, tmp_path / "local.db")


def test_ticket_values_maps_empty_cells_to_null() -> None:
    row = dict.fromkeys(TICKET_FIELDS, "")
    row.update(
        ticket_id="TCK-000001",
        fecha_apertura="2026-10-31 10:00:00",
        categoria="Accesos",
        subcategoria="VPN",
        prioridad="P3",
        sucursal="Puebla 01",
        area="Caja",
        canal="portal",
        sla_horas="24",
        anio_mes="2026-10",
        solucion="Reconfigurar VPN.",
        es_repetitivo="1",
        idioma="es",
        estado="abierto",
    )
    values = dict(zip(TICKET_FIELDS, ticket_values(row), strict=True))
    assert values["fecha_cierre"] is None
    assert values["sla_cumplido"] is None
    assert values["horas_resolucion"] is None
    assert values["es_repetitivo"] == 1
    assert values["sla_horas"] == 24
