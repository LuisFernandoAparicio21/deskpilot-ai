"""Integration: ``POST /tickets`` over a temporary SQLite database (S9, RF-16, RN-01..05)."""

from __future__ import annotations

import logging
import re
import shutil
import sqlite3
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr

from src.api import ApiServices, create_app
from src.api.repository import (
    NewTicket,
    SqlTicketRepository,
    TicketSource,
    WriteTarget,
    build_repository,
)
from src.api.schemas import CrearTicketRequest
from src.api.ticket_service import TicketService
from src.ingestion.sqlite_loader import TICKETS_NUEVOS_COLUMNS, load_sqlite
from src.ingestion.ticket_generator import DATE_FORMAT, generate_dataset
from src.llm import LLMError
from src.utils.config import Secrets, Settings, load_settings
from tests.unit.conftest import KEY_HEADER, FakeSearch, Probe
from tests.unit.test_classification import FakeLLM, _json

N_TICKETS = 300
GOOD: dict[str, Any] = {
    "descripcion": "La VPN es intermitente desde ayer",
    "sucursal": "Centro",
    "area": "Caja",
}
SECRETS = {
    "password": ("mi contraseña es Zx9secretoPW", "Zx9secretoPW"),
    "pin": ("mi NIP es 482193", "482193"),
    "card": ("la tarjeta 4539 1488 0343 6467 fue rechazada", "4539 1488 0343 6467"),
    "curp": ("mi CURP es HEGG560427MVZRRL04", "HEGG560427MVZRRL04"),
    "token": ("token: aB3xKq9ZpLm2Wv7Rt", "aB3xKq9ZpLm2Wv7Rt"),
}


@pytest.fixture(scope="module")
def template_db(tmp_path_factory: pytest.TempPathFactory) -> Path:
    base = tmp_path_factory.mktemp("create")
    settings = load_settings(env_file=base / "missing.env")
    generate_dataset(
        settings.data.seed,
        N_TICKETS,
        base / "raw",
        base / "sample",
        settings.sla_horas.model_dump(),
    )
    db = base / "template.db"
    load_sqlite(base / "raw", db)
    return db


@pytest.fixture
def db(template_db: Path, tmp_path: Path) -> Path:
    copy = tmp_path / "deskpilot.db"
    shutil.copy(template_db, copy)
    return copy


def _settings(db: Path) -> Settings:
    settings = load_settings(env_file=db.parent / "missing.env")
    paths = settings.paths.model_copy(update={"sqlite_db": db})
    secrets = Secrets(api_key=SecretStr(KEY_HEADER["X-API-Key"]))
    return settings.model_copy(update={"paths": paths, "secrets": secrets})


def _app(settings: Settings, llm: FakeLLM | None = None) -> TestClient:
    repository = build_repository(settings)
    services = ApiServices(
        answers=FakeSearch(),
        repository=repository,
        index_probe=Probe(),
        tickets=TicketService(repository, llm or FakeLLM(error=LLMError("off")), settings),
    )
    return TestClient(create_app(settings, services), raise_server_exceptions=False)


@pytest.fixture
def client(db: Path) -> Iterator[TestClient]:
    with _app(_settings(db)) as c:
        yield c


def _sql(db: Path, sql: str, params: tuple[Any, ...] = ()) -> list[tuple[Any, ...]]:
    conn = sqlite3.connect(db)
    try:
        return conn.execute(sql, params).fetchall()
    finally:
        conn.close()


def _rows(db: Path) -> list[dict[str, Any]]:
    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    try:
        return [dict(r) for r in conn.execute("SELECT * FROM tickets_nuevos ORDER BY rowid")]
    finally:
        conn.close()


def _post(client: TestClient, body: dict[str, Any]) -> Any:
    return client.post("/tickets", json=body, headers=KEY_HEADER)


# --- happy path and consistency --------------------------------------------------------------


def test_created_ticket_is_stored_and_matches_the_response(client: TestClient, db: Path) -> None:
    before = datetime.now(UTC).replace(tzinfo=None)  # the API stores naive UTC
    response = _post(client, {**GOOD, "canal": "portal"})
    assert response.status_code == 201
    body = response.json()
    assert re.fullmatch(r"TCK-\d{6}", body["ticket_id"])
    (row,) = _rows(db)
    assert set(row) == set(TICKETS_NUEVOS_COLUMNS)
    assert row["ticket_id"] == body["ticket_id"]
    assert (row["categoria"], row["subcategoria"]) == ("Conectividad", "VPN")
    assert (row["prioridad"], row["sla_horas"], row["estado"]) == ("P3", 24, "abierto")
    assert (row["sucursal"], row["area"], row["canal"]) == ("Centro", "Caja", "portal")
    assert row["idioma"] == "es"
    assert row["descripcion"] == GOOD["descripcion"]
    assert row["fecha_cierre"] is None
    assert row["sla_cumplido"] is None
    assert row["es_repetitivo"] == 0
    opened = datetime.strptime(row["fecha_apertura"], DATE_FORMAT)
    assert row["anio_mes"] == opened.strftime("%Y-%m")
    assert abs(opened - before) < timedelta(minutes=5)
    assert datetime.fromisoformat(body["fecha_apertura"]) == opened
    assert datetime.fromisoformat(body["fecha_limite_sla"]) == opened + timedelta(hours=24)


def test_created_ticket_can_be_queried_with_the_same_id(client: TestClient) -> None:
    created = _post(client, {**GOOD, "descripcion": "Toda la sucursal sin internet"}).json()
    status = client.get(f"/tickets/{created['ticket_id']}", headers=KEY_HEADER)
    assert status.status_code == 200
    body = status.json()
    assert body["ticket_id"] == created["ticket_id"]
    assert body["estado"] == "abierto"
    assert body["prioridad"] == created["prioridad"] == "P1"
    assert body["sla_horas"] == created["sla_horas"] == 4
    assert body["fecha_cierre"] is None
    assert body["sla_cumplido"] is None
    assert body["fecha_apertura"] == created["fecha_apertura"]
    assert body["fecha_limite_sla"] == created["fecha_limite_sla"]


def test_historical_tickets_are_untouched(client: TestClient, db: Path) -> None:
    before = _sql(db, "SELECT * FROM tickets ORDER BY ticket_id")
    for _ in range(5):
        _post(client, GOOD)
    assert _sql(db, "SELECT * FROM tickets ORDER BY ticket_id") == before
    assert len(_rows(db)) == 5


@pytest.mark.parametrize(
    ("text", "priority", "hours"),
    [
        ("Toda la sucursal sin red", "P1", 4),
        ("No puedo entrar al sistema", "P2", 8),
        ("La VPN es intermitente", "P3", 24),
        ("Necesito instalar Adobe Reader", "P4", 72),
    ],
)
def test_sla_is_4_8_24_72_hours_by_priority_in_the_stored_row(
    client: TestClient, db: Path, text: str, priority: str, hours: int
) -> None:
    body = _post(client, {**GOOD, "descripcion": text}).json()
    assert (body["prioridad"], body["sla_horas"]) == (priority, hours)
    assert _sql(db, "SELECT prioridad, sla_horas FROM tickets_nuevos") == [(priority, hours)]


@pytest.mark.parametrize(
    ("text", "reason"),
    [
        ("Veo cargos no reconocidos en la cuenta de un cliente", "fraud"),
        ("Alguien más entró a mi cuenta, acceso no autorizado", "unauthorized_access"),
        ("The cash register is frozen", "cash_system"),
    ],
)
def test_mandatory_escalation_is_stored_as_p1_and_the_llm_is_not_asked(
    db: Path, text: str, reason: str
) -> None:
    llm = FakeLLM(reply=_json("Software", "P4"))
    with _app(_settings(db), llm) as client:
        body = _post(client, {**GOOD, "descripcion": text}).json()
    assert (body["prioridad"], body["escalado"], body["motivo_escalamiento"]) == (
        "P1",
        True,
        reason,
    )
    assert body["sla_horas"] == 4
    assert body["mode"] == "rules"
    assert llm.prompts == []
    assert _sql(db, "SELECT prioridad, sla_horas FROM tickets_nuevos") == [("P1", 4)]


def test_llm_mode_is_reported_and_stored_category_comes_from_the_model(db: Path) -> None:
    llm = FakeLLM(reply=_json("Software", "P3"))
    with _app(_settings(db), llm) as client:
        body = _post(client, {**GOOD, "descripcion": "Necesito ayuda con un programa raro"}).json()
    assert (body["mode"], body["categoria"], body["prioridad"]) == ("llm", "Software", "P3")
    assert _sql(db, "SELECT categoria, prioridad FROM tickets_nuevos") == [("Software", "P3")]


@pytest.mark.parametrize(
    "reply",
    [
        "not json at all",
        _json("Finanzas", "P3"),
        _json("Software", "P9"),
        _json("Software", "P1"),  # raising a P4 ticket to P1
        _json("Software", "P2"),  # two levels from P4
    ],
)
def test_untrustworthy_llm_output_never_changes_the_rule_priority(db: Path, reply: str) -> None:
    with _app(_settings(db), FakeLLM(reply=reply)) as client:
        body = _post(client, {**GOOD, "descripcion": "Necesito instalar Adobe Reader"}).json()
    assert body["prioridad"] == "P4"
    assert body["sla_horas"] == 72
    assert body["escalado"] is False
    assert _sql(db, "SELECT prioridad FROM tickets_nuevos") == [("P4",)]


# --- RN-05: sensitive data --------------------------------------------------------------------


@pytest.mark.parametrize("kind", sorted(SECRETS))
def test_secret_is_nowhere_in_the_database_response_logs_or_llm_prompt(
    db: Path, caplog: pytest.LogCaptureFixture, kind: str
) -> None:
    sentence, secret = SECRETS[kind]
    llm = FakeLLM(reply=_json("Accesos", "P3"))
    with caplog.at_level(logging.DEBUG), _app(_settings(db), llm) as client:
        response = _post(client, {**GOOD, "descripcion": f"No puedo iniciar sesión, {sentence}"})
    assert response.status_code == 201
    assert response.json()["sensitive_data_warning"] is True
    assert secret not in response.text
    (row,) = _rows(db)
    assert "[REDACTED:" in row["descripcion"]
    assert not any(secret in str(value) for value in row.values())
    with closing(sqlite3.connect(db)) as conn:
        dump = "\n".join(conn.iterdump())  # every table, every column
    assert secret not in dump
    assert len(llm.prompts) == 1
    assert secret not in " ".join(llm.prompts[0])
    logged = "\n".join(f"{r.getMessage()} {r.__dict__} {r.exc_info}" for r in caplog.records)
    assert secret not in logged


def test_a_clean_description_is_stored_verbatim_without_warning(
    client: TestClient, db: Path
) -> None:
    plain = _post(client, GOOD).json()
    assert plain["sensitive_data_warning"] is False
    assert _rows(db)[-1]["descripcion"] == GOOD["descripcion"]


# --- abuse ------------------------------------------------------------------------------------


def test_sql_injection_in_description_is_stored_as_text_and_tables_survive(
    client: TestClient, db: Path
) -> None:
    payload = "x'); DROP TABLE tickets_nuevos; DELETE FROM tickets; --"
    historical = _sql(db, "SELECT COUNT(*) FROM tickets")[0][0]
    response = _post(client, {**GOOD, "descripcion": payload})
    assert response.status_code == 201
    assert _rows(db)[0]["descripcion"] == payload
    assert _sql(db, "SELECT COUNT(*) FROM tickets")[0][0] == historical


@pytest.mark.parametrize("field", ["sucursal", "area"])
@pytest.mark.parametrize(
    "value", ["Centro'; DROP TABLE tickets_nuevos;--", "' OR '1'='1", 'a" OR 1=1 --', "x;y"]
)
def test_sql_injection_in_name_fields_is_rejected_before_the_database(
    client: TestClient, db: Path, field: str, value: str
) -> None:
    response = _post(client, {**GOOD, field: value})
    assert response.status_code == 422
    assert _rows(db) == []
    assert _sql(db, "SELECT COUNT(*) FROM tickets_nuevos") == [(0,)]


def test_abuse_requests_leave_the_table_empty(client: TestClient, db: Path) -> None:
    assert client.post("/tickets", json=GOOD).status_code == 401
    assert _post(client, {**GOOD, "descripcion": "abc"}).status_code == 422
    assert _post(client, {**GOOD, "extra": 1}).status_code == 422
    assert _post(client, {**GOOD, "descripcion": "a" * 3000}).status_code == 422
    big = client.post("/tickets", json={**GOOD, "descripcion": "a" * 30_000}, headers=KEY_HEADER)
    assert big.status_code == 413
    malformed = client.post(
        "/tickets", content=b"{", headers={**KEY_HEADER, "Content-Type": "application/json"}
    )
    assert malformed.status_code == 422
    assert _rows(db) == []


# --- unique ids -------------------------------------------------------------------------------


def _service(settings: Settings) -> TicketService:
    return TicketService(build_repository(settings), FakeLLM(error=LLMError("off")), settings)


def test_400_concurrent_inserts_give_400_unique_well_formed_ids(db: Path) -> None:
    service = _service(_settings(db))
    request = CrearTicketRequest(**GOOD)
    with ThreadPoolExecutor(max_workers=16) as pool:
        ids = list(pool.map(lambda _: service.create(request).ticket_id, range(400)))
    assert len(set(ids)) == 400
    assert all(re.fullmatch(r"TCK-\d{6}", i) for i in ids)
    assert {r[0] for r in _sql(db, "SELECT ticket_id FROM tickets_nuevos")} == set(ids)
    assert _sql(db, "SELECT COUNT(*) FROM tickets_nuevos") == [(400,)]
    historical = {r[0] for r in _sql(db, "SELECT ticket_id FROM tickets")}
    assert historical.isdisjoint(ids)


def test_concurrent_api_requests_are_all_created(db: Path) -> None:
    with _app(_settings(db)) as client, ThreadPoolExecutor(max_workers=8) as pool:
        responses = list(pool.map(lambda _: _post(client, GOOD), range(48)))
    assert [r.status_code for r in responses] == [201] * 48
    assert len({r.json()["ticket_id"] for r in responses}) == 48
    assert _sql(db, "SELECT COUNT(*) FROM tickets_nuevos") == [(48,)]


def _writable(db: Path) -> Any:
    return lambda: sqlite3.connect(f"{db.resolve().as_uri()}?mode=rw", uri=True, timeout=5)


def _repository_with_ids(db: Path, ids: list[str]) -> SqlTicketRepository:
    queue = iter(ids)
    source = TicketSource(_writable(db), "tickets_nuevos")
    target = WriteTarget(
        _writable(db), "tickets_nuevos", ("tickets_nuevos", "tickets"), "BEGIN IMMEDIATE"
    )
    return SqlTicketRepository(
        [TicketSource(_writable(db), "tickets"), source],
        backend="sqlite",
        writer=target,
        id_factory=lambda: next(queue),
    )


def _new(**kw: Any) -> NewTicket:
    base: dict[str, Any] = {
        "fecha_apertura": datetime(2026, 3, 2, 9, 0, 0),
        "categoria": "General",
        "subcategoria": "Consulta general",
        "prioridad": "P4",
        "sucursal": "Centro",
        "area": "Caja",
        "canal": "Teams",
        "sla_horas": 72,
        "idioma": "es",
        "descripcion": "consulta",
    }
    return NewTicket(**{**base, **kw})


def test_forced_collision_with_a_historical_id_retries_with_a_new_one(db: Path) -> None:
    historical = _sql(db, "SELECT ticket_id FROM tickets LIMIT 1")[0][0]
    repo = _repository_with_ids(db, [historical, "TCK-777777"])
    assert repo.create_ticket(_new()) == "TCK-777777"
    assert _sql(db, "SELECT ticket_id FROM tickets_nuevos") == [("TCK-777777",)]
    assert _sql(db, "SELECT COUNT(*) FROM tickets WHERE ticket_id = ?", (historical,)) == [(1,)]


def test_forced_collision_with_a_new_ticket_retries_and_keeps_both_rows(db: Path) -> None:
    repo = _repository_with_ids(db, ["TCK-555555", "TCK-555555", "TCK-555556"])
    first = repo.create_ticket(_new(descripcion="primero"))
    second = repo.create_ticket(_new(descripcion="segundo"))
    assert (first, second) == ("TCK-555555", "TCK-555556")
    assert _sql(db, "SELECT ticket_id, descripcion FROM tickets_nuevos ORDER BY rowid") == [
        ("TCK-555555", "primero"),
        ("TCK-555556", "segundo"),
    ]


def test_endless_collisions_become_503_and_store_nothing(db: Path) -> None:
    historical = _sql(db, "SELECT ticket_id FROM tickets LIMIT 1")[0][0]
    settings = _settings(db)
    repo = _repository_with_ids(db, [historical] * 20)
    services = ApiServices(
        answers=FakeSearch(),
        repository=repo,
        index_probe=Probe(),
        tickets=TicketService(repo, FakeLLM(error=LLMError("off")), settings),
    )
    with TestClient(create_app(settings, services), raise_server_exceptions=False) as client:
        response = _post(client, GOOD)
    assert response.status_code == 503
    assert _rows(db) == []


# --- database failure -------------------------------------------------------------------------


def test_unreachable_database_is_503_with_no_trace_or_user_text(
    tmp_path: Path, db: Path, caplog: pytest.LogCaptureFixture
) -> None:
    settings = _settings(db)
    with _app(settings) as client:
        db.unlink()  # the file disappears after start-up
        secret = "MARCA-UNICA-4455"
        with caplog.at_level(logging.DEBUG):
            response = _post(client, {**GOOD, "descripcion": f"La VPN falla {secret}"})
    assert response.status_code == 503
    assert response.json()["code"] == "database_unavailable"
    assert secret not in response.text
    assert "Traceback" not in response.text
    assert str(tmp_path) not in response.text
    logged = "\n".join(f"{r.getMessage()} {r.__dict__} {r.exc_info}" for r in caplog.records)
    assert secret not in logged
    assert str(tmp_path) not in logged
    assert not db.exists()  # mode=rw never creates the database file


def test_missing_table_is_503_and_rolls_back(db: Path) -> None:
    conn = sqlite3.connect(db)
    conn.execute("DROP TABLE tickets_nuevos")
    conn.commit()
    conn.close()
    with _app(_settings(db)) as client:
        response = _post(client, GOOD)
    assert response.status_code == 503
    assert _sql(db, "SELECT COUNT(*) FROM tickets") == [(N_TICKETS,)]
