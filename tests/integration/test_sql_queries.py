"""Integration: generate data -> load SQLite -> run the 10 business queries (S5, RF-20).

Uses the seed and size of config.yaml, written to ``tmp_path``, so the business sanity
checks below run on the same data as ``python main.py load-db --run-sql``.
"""

from __future__ import annotations

import pytest

from src.ingestion.sqlite_loader import load_sqlite
from src.ingestion.ticket_generator import generate_dataset
from src.utils.config import load_settings
from src.utils.db import SQL_DIR, QueryResult, list_query_files, run_sql_file, sqlite_connection


@pytest.fixture(scope="module")
def results(tmp_path_factory: pytest.TempPathFactory) -> dict[str, QueryResult]:
    base = tmp_path_factory.mktemp("sql")
    settings = load_settings(env_file=base / "missing.env")
    generate_dataset(
        settings.data.seed,
        settings.data.n_tickets,
        base / "raw",
        base / "sample",
        settings.sla_horas.model_dump(),
    )
    db = base / "deskpilot.db"
    load_sqlite(base / "raw", db)
    with sqlite_connection(db) as conn:
        return {path.stem[:2]: run_sql_file(conn, path) for path in list_query_files(SQL_DIR)}


def _rows(result: QueryResult) -> list[dict[str, object]]:
    return [dict(zip(result.columns, row, strict=True)) for row in result.rows]


def test_all_ten_queries_return_rows(results: dict[str, QueryResult]) -> None:
    assert sorted(results) == [f"{i:02d}" for i in range(1, 11)]
    empty = [r.name for r in results.values() if not r.rows]
    assert empty == []


def test_expected_row_counts(results: dict[str, QueryResult]) -> None:
    assert len(results["01"].rows) == 10  # top 10 via ROW_NUMBER
    assert len(results["03"].rows) == 120  # one row per branch
    assert len(results["06"].rows) == 12  # 12 months of the period
    assert len(results["08"].rows) == 2  # local vs foranea
    assert [r["prioridad"] for r in _rows(results["10"])] == ["P1", "P2", "P3", "P4"]


def test_foraneas_have_worse_sla(results: dict[str, QueryResult]) -> None:
    by_type = {r["tipo_sucursal"]: r for r in _rows(results["08"])}
    local, foranea = by_type["local"], by_type["foranea"]
    assert isinstance(local["pct_sla_cumplido"], float)
    assert isinstance(foranea["pct_sla_cumplido"], float)
    assert foranea["pct_sla_cumplido"] <= local["pct_sla_cumplido"] - 10  # S3: >= 10 pp
    assert local["diferencia_vs_local_pp"] == 0


def test_payday_days_have_more_unlocks(results: dict[str, QueryResult]) -> None:
    by_type = {r["tipo_dia"]: r for r in _rows(results["07"])}
    quincena, resto = by_type["quincena"], by_type["resto"]
    assert isinstance(quincena["desbloqueos_por_dia"], float)
    assert isinstance(resto["desbloqueos_por_dia"], float)
    assert quincena["desbloqueos_por_dia"] > resto["desbloqueos_por_dia"]
    assert isinstance(quincena["veces_vs_resto"], float)
    assert quincena["veces_vs_resto"] >= 1.5  # S3 threshold


def test_top_ranking_is_sorted_and_cumulative(results: dict[str, QueryResult]) -> None:
    rows = _rows(results["01"])
    tickets = [r["tickets"] for r in rows]
    assert tickets == sorted(tickets, reverse=True)  # type: ignore[type-var]
    assert [r["posicion"] for r in rows] == list(range(1, 11))
    assert rows[-1]["pct_acumulado"] <= 100  # type: ignore[operator]


def test_automatable_tickets_only_in_kb_subcategories(results: dict[str, QueryResult]) -> None:
    rows = _rows(results["05"])
    assert all(r["tickets_automatizables"] == 0 for r in rows if r["tiene_articulo"] == 0)
    assert sum(r["tickets_automatizables"] for r in rows) > 0  # type: ignore[misc]


def test_automatable_share_is_credible(results: dict[str, QueryResult]) -> None:
    """RN-06 share stays between 45% and 55% of all tickets (realistic L2 escalation)."""
    rows = _rows(results["05"])
    automatable = sum(int(r["tickets_automatizables"]) for r in rows)  # type: ignore[call-overload]
    total = sum(int(r["tickets"]) for r in rows)  # type: ignore[call-overload]
    assert 0.45 <= automatable / total <= 0.55
