"""Integration: API over the generated dataset loaded into SQLite (S8, RF-17, RF-19, RF-26)."""

from __future__ import annotations

import sqlite3
from collections import Counter
from collections.abc import Iterator
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr

from src.api import ApiServices, create_app
from src.api.repository import build_repository
from src.ingestion.sqlite_loader import TICKETS_NUEVOS_COLUMNS, load_sqlite
from src.ingestion.ticket_generator import DATE_FORMAT, generate_dataset
from src.utils.config import Secrets, Settings, load_settings
from tests.unit.conftest import KEY_HEADER, FakeSearch, Probe

API_KEY = KEY_HEADER["X-API-Key"]
N_TICKETS = 1500


@pytest.fixture(scope="module")
def db_path(tmp_path_factory: pytest.TempPathFactory) -> Path:
    base = tmp_path_factory.mktemp("api")
    settings = load_settings(env_file=base / "missing.env")
    generate_dataset(
        settings.data.seed,
        N_TICKETS,
        base / "raw",
        base / "sample",
        settings.sla_horas.model_dump(),
    )
    db = base / "deskpilot.db"
    load_sqlite(base / "raw", db)
    return db


def _settings(db: Path) -> Settings:
    settings = load_settings(env_file=db.parent / "missing.env")
    paths = settings.paths.model_copy(update={"sqlite_db": db})
    return settings.model_copy(
        update={"paths": paths, "secrets": Secrets(api_key=SecretStr(API_KEY))}
    )


def _services(settings: Settings) -> ApiServices:
    return ApiServices(
        answers=FakeSearch(), repository=build_repository(settings), index_probe=Probe()
    )


@pytest.fixture
def client(db_path: Path) -> Iterator[TestClient]:
    settings = _settings(db_path)
    with TestClient(create_app(settings, _services(settings)), raise_server_exceptions=False) as c:
        yield c


def _sql(db: Path, sql: str, params: tuple[Any, ...] = ()) -> list[tuple[Any, ...]]:
    conn = sqlite3.connect(db)
    try:
        return conn.execute(sql, params).fetchall()
    finally:
        conn.close()


def _get(client: TestClient, url: str, **params: str) -> Any:
    return client.get(url, params=params or None, headers=KEY_HEADER)


# --- tickets ---------------------------------------------------------------------------------


@pytest.mark.parametrize("estado", ["abierto", "en_proceso", "resuelto", "cerrado"])
def test_ticket_status_matches_the_database_for_every_state(
    client: TestClient, db_path: Path, estado: str
) -> None:
    row = _sql(
        db_path,
        "SELECT ticket_id, estado, prioridad, fecha_apertura, fecha_cierre, sla_horas, "
        "sla_cumplido FROM tickets WHERE estado = ? ORDER BY ticket_id LIMIT 1",
        (estado,),
    )
    assert row, f"the dataset has no {estado} ticket"
    ticket_id, _, prioridad, opened, closed, sla, met = row[0]
    response = _get(client, f"/tickets/{ticket_id}")
    assert response.status_code == 200
    body = response.json()
    assert body["ticket_id"] == ticket_id
    assert body["estado"] == estado
    assert body["prioridad"] == prioridad
    assert body["sla_horas"] == sla
    opened_at = datetime.strptime(opened, DATE_FORMAT)
    assert datetime.fromisoformat(body["fecha_apertura"]) == opened_at
    assert datetime.fromisoformat(body["fecha_limite_sla"]) == opened_at + timedelta(hours=sla)
    if closed is None:
        assert body["fecha_cierre"] is None
        assert body["sla_cumplido"] is None
    else:
        closed_at = datetime.strptime(closed, DATE_FORMAT)
        assert datetime.fromisoformat(body["fecha_cierre"]) == closed_at
        assert body["sla_cumplido"] is bool(met)


def test_sla_flag_agrees_with_the_closing_date_for_closed_tickets(
    client: TestClient, db_path: Path
) -> None:
    ids = _sql(db_path, "SELECT ticket_id FROM tickets WHERE sla_cumplido IS NOT NULL LIMIT 60")
    assert len(ids) == 60
    for (ticket_id,) in ids:
        body = _get(client, f"/tickets/{ticket_id}").json()
        closed = datetime.fromisoformat(body["fecha_cierre"])
        within = closed <= datetime.fromisoformat(body["fecha_limite_sla"])
        assert body["sla_cumplido"] is within, ticket_id


def test_ticket_response_has_no_other_fields(client: TestClient, db_path: Path) -> None:
    ticket_id = _sql(db_path, "SELECT ticket_id FROM tickets LIMIT 1")[0][0]
    body = _get(client, f"/tickets/{ticket_id}").json()
    assert set(body) == {
        "ticket_id", "estado", "prioridad", "fecha_apertura", "fecha_cierre",
        "sla_horas", "fecha_limite_sla", "sla_cumplido",
    }  # fmt: skip


def test_unknown_ticket_is_404_and_reveals_nothing(client: TestClient) -> None:
    response = _get(client, "/tickets/TCK-999999")
    assert response.status_code == 404
    assert response.json()["code"] == "ticket_not_found"
    assert "TCK" not in response.json()["message"]
    assert set(response.json()) == {"code", "message", "request_id", "details"}


def test_sql_injection_in_ticket_id_cannot_match_or_damage(
    client: TestClient, db_path: Path
) -> None:
    for payload in (
        "x%27%20OR%20%271%27=%271",
        "TCK-000001%27--",
        "1%20OR%201=1",
        "a;DROP%20TABLE",
    ):
        assert _get(client, f"/tickets/{payload}").status_code == 422
    assert _sql(db_path, "SELECT COUNT(*) FROM tickets")[0][0] == N_TICKETS


def test_ticket_from_tickets_nuevos_is_found(client: TestClient, db_path: Path) -> None:
    values: dict[str, Any] = {
        "ticket_id": "NEW-0001", "fecha_apertura": "2026-11-02 08:30:00", "fecha_cierre": None,
        "categoria": "Accesos", "subcategoria": "Reseteo de contraseña", "prioridad": "P1",
        "sucursal": "Nuevo", "area": "Caja", "canal": "portal", "sla_horas": 4,
        "sla_cumplido": None, "horas_resolucion": None, "anio_mes": "2026-11", "solucion": None,
        "es_repetitivo": 0, "idioma": "es", "estado": "abierto", "descripcion": "no entra",
    }  # fmt: skip
    assert tuple(values) == TICKETS_NUEVOS_COLUMNS
    marks = ",".join("?" * len(values))
    conn = sqlite3.connect(db_path)
    try:
        conn.execute(f"INSERT INTO tickets_nuevos VALUES ({marks})", tuple(values.values()))
        conn.commit()
        body = _get(client, "/tickets/NEW-0001").json()
        assert body["estado"] == "abierto"
        assert body["prioridad"] == "P1"
        assert datetime.fromisoformat(body["fecha_limite_sla"]) == datetime(2026, 11, 2, 12, 30)
        assert "descripcion" not in body
        assert "no entra" not in str(body)
    finally:
        conn.execute("DELETE FROM tickets_nuevos WHERE ticket_id = 'NEW-0001'")
        conn.commit()
        conn.close()


# --- metrics ---------------------------------------------------------------------------------


def _expected_metrics(db: Path, column: str, name: str) -> dict[str, Any]:
    """Independent computation: raw rows pulled with SQL, aggregated in Python."""
    rows = _sql(
        db,
        f"SELECT categoria, sla_cumplido, horas_resolucion FROM tickets WHERE {column} = ?",
        (name,),
    )
    closed = [r for r in rows if r[1] is not None]
    hours = [r[2] for r in rows if r[2] is not None]
    counts = Counter(r[0] for r in rows)
    ranked = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))[:3]
    return {
        "total": len(rows),
        "closed": len(closed),
        "pct": 100 * sum(r[1] for r in closed) / len(closed) if closed else None,
        "avg": sum(hours) / len(hours) if hours else None,
        "top": ranked,
    }


def _names(db: Path, column: str) -> list[str]:
    sql = f"SELECT {column} FROM tickets GROUP BY {column} ORDER BY COUNT(*) DESC, {column}"
    return [r[0] for r in _sql(db, sql)]


@pytest.mark.parametrize("column", ["area", "sucursal"])
def test_metrics_match_the_database(client: TestClient, db_path: Path, column: str) -> None:
    names = _names(db_path, column)
    assert len(names) >= 5
    for name in names[:12]:
        response = _get(client, "/metricas", **{column: name})
        assert response.status_code == 200, name
        body = response.json()
        want = _expected_metrics(db_path, column, name)
        assert body["scope"] == column
        assert body["name"] == name
        assert body["total_tickets"] == want["total"]
        assert body["closed_tickets"] == want["closed"]
        assert body["sla_cumplido_pct"] == pytest.approx(want["pct"], abs=0.051)
        assert body["avg_horas_resolucion"] == pytest.approx(want["avg"], abs=0.051)
        assert [(c["categoria"], c["tickets"]) for c in body["top_categorias"]] == want["top"]


def test_metrics_values_are_plausible_and_consistent(client: TestClient, db_path: Path) -> None:
    body = _get(client, "/metricas", area=_names(db_path, "area")[0]).json()
    assert 0 < body["total_tickets"] <= N_TICKETS
    assert body["closed_tickets"] <= body["total_tickets"]
    assert 0 <= body["sla_cumplido_pct"] <= 100
    assert body["avg_horas_resolucion"] > 0
    assert len(body["top_categorias"]) == 3
    tickets = [c["tickets"] for c in body["top_categorias"]]
    assert tickets == sorted(tickets, reverse=True)
    assert sum(tickets) <= body["total_tickets"]


def test_metrics_of_all_areas_add_up_to_the_dataset(client: TestClient, db_path: Path) -> None:
    total = sum(
        _get(client, "/metricas", area=a).json()["total_tickets"] for a in _names(db_path, "area")
    )
    assert total == _sql(db_path, "SELECT COUNT(*) FROM tickets")[0][0] == N_TICKETS


def test_unknown_name_is_404_for_area_and_sucursal(client: TestClient) -> None:
    for param in ("area", "sucursal"):
        response = _get(client, "/metricas", **{param: "No Existe"})
        assert response.status_code == 404
        assert response.json()["code"] == "not_found"


def test_area_and_sucursal_namespaces_are_not_mixed(client: TestClient, db_path: Path) -> None:
    assert _get(client, "/metricas", sucursal=_names(db_path, "area")[0]).status_code == 404


def test_values_that_pass_validation_but_look_like_sql_match_nothing(
    client: TestClient, db_path: Path
) -> None:
    for payload in ("1 OR 1", "Caja OR area", "--", "a-b-c", "_"):
        assert _get(client, "/metricas", area=payload).status_code == 404, payload
    assert _sql(db_path, "SELECT COUNT(*) FROM tickets")[0][0] == N_TICKETS


def test_both_or_none_of_area_and_sucursal_is_422(client: TestClient, db_path: Path) -> None:
    area, sucursal = _names(db_path, "area")[0], _names(db_path, "sucursal")[0]
    assert _get(client, "/metricas", area=area, sucursal=sucursal).status_code == 422
    assert _get(client, "/metricas").status_code == 422


# --- availability ------------------------------------------------------------------------------


def test_health_ok_with_the_real_database(client: TestClient) -> None:
    body = client.get("/health").json()
    assert body["status"] == "ok"
    assert body["database"] == {"status": "ok"}


def test_missing_database_gives_503_and_degraded_health(tmp_path: Path) -> None:
    settings = _settings(tmp_path / "absent.db")
    with TestClient(create_app(settings, _services(settings))) as client:
        for url in ("/tickets/TCK-000001", "/metricas?area=Caja"):
            response = client.get(url, headers=KEY_HEADER)
            assert response.status_code == 503
            assert response.json()["code"] == "database_unavailable"
            assert "absent.db" not in response.text
        health = client.get("/health").json()
        assert health["status"] == "degraded"
        assert health["database"] == {"status": "unavailable"}
    assert not (tmp_path / "absent.db").exists()


def test_database_without_the_tables_is_503(tmp_path: Path) -> None:
    empty = tmp_path / "empty.db"
    sqlite3.connect(empty).close()
    settings = _settings(empty)
    with TestClient(create_app(settings, _services(settings))) as client:
        assert client.get("/tickets/TCK-000001", headers=KEY_HEADER).status_code == 503
        assert client.get("/health").json()["database"] == {"status": "unavailable"}


def test_the_api_connection_is_read_only(db_path: Path) -> None:
    repo = build_repository(_settings(db_path))
    conn = repo._sources[0].connect()  # type: ignore[attr-defined]
    try:
        with pytest.raises(sqlite3.OperationalError):
            conn.cursor().execute("DELETE FROM tickets")
    finally:
        conn.close()
    assert _sql(db_path, "SELECT COUNT(*) FROM tickets")[0][0] == N_TICKETS
