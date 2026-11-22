"""``POST /tickets``: auth order, validation, abuse, 413, 503 and log hygiene (S9, RNF-04/05/06)."""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

import pytest
from fastapi.testclient import TestClient

from src.api.repository import RepositoryUnavailableError
from tests.unit.conftest import KEY_HEADER, Env

GOOD: dict[str, Any] = {
    "descripcion": "La VPN es intermitente desde ayer",
    "sucursal": "Centro",
    "area": "Caja",
}


def _post(client: TestClient, body: Any, headers: dict[str, str] | None = KEY_HEADER) -> Any:
    return client.post("/tickets", json=body, headers=headers)


def _logs(caplog: pytest.LogCaptureFixture) -> str:
    return "\n".join(
        f"{r.name} {r.getMessage()} {r.__dict__} {r.exc_info}"
        for r in caplog.records
        if r.name.startswith("src")
    )


def test_create_returns_201_with_the_documented_fields(client: TestClient, env: Env) -> None:
    response = _post(client, GOOD)
    assert response.status_code == 201
    body = response.json()
    assert set(body) == {
        "ticket_id", "estado", "categoria", "subcategoria", "prioridad", "sla_horas",
        "fecha_apertura", "fecha_limite_sla", "escalado", "motivo_escalamiento",
        "sensitive_data_warning", "mode",
    }  # fmt: skip
    assert body["estado"] == "abierto"
    assert (body["categoria"], body["prioridad"], body["sla_horas"]) == ("Conectividad", "P3", 24)
    assert body["mode"] == "rules"
    assert len(env.repo.created) == 1


def test_response_never_returns_the_description(client: TestClient) -> None:
    response = _post(client, {**GOOD, "descripcion": "La VPN falla MARCA-UNICA-9931"})
    assert response.status_code == 201
    assert "MARCA-UNICA-9931" not in response.text
    assert "descripcion" not in response.json()


def test_canal_defaults_to_teams_and_accepts_the_known_channels(
    client: TestClient, env: Env
) -> None:
    for canal in ("portal", "correo", "teléfono", "Teams"):
        assert _post(client, {**GOOD, "canal": canal}).status_code == 201
    _post(client, GOOD)
    assert [t.canal for t in env.repo.created] == ["portal", "correo", "teléfono", "Teams", "Teams"]
    assert _post(client, {**GOOD, "canal": "fax"}).status_code == 422


@pytest.mark.parametrize(
    "headers", [None, {"X-API-Key": "wrong-key-0123456789"}, {"X-API-Key": ""}]
)
def test_missing_or_wrong_key_is_401_and_nothing_is_stored(
    client: TestClient, env: Env, headers: dict[str, str] | None
) -> None:
    response = _post(client, GOOD, headers=headers)
    assert response.status_code == 401
    assert response.json()["code"] == "unauthorized"
    assert env.repo.created == []


@pytest.mark.parametrize("body", [{}, {"descripcion": "x"}, {"extra": 1}])
def test_401_comes_before_422_so_an_invalid_body_leaks_no_schema(
    client: TestClient, body: dict[str, Any]
) -> None:
    response = _post(client, body, headers=None)
    assert response.status_code == 401
    assert response.json()["details"] is None


@pytest.mark.parametrize(
    "body",
    [
        {},
        {"descripcion": GOOD["descripcion"], "sucursal": "Centro"},  # no area
        {"descripcion": GOOD["descripcion"], "area": "Caja"},  # no sucursal
        {**GOOD, "descripcion": "abcd"},  # shorter than 5
        {**GOOD, "descripcion": "     "},  # blank after trimming
        {**GOOD, "descripcion": "a" * 2001},  # over api.max_description_chars
        {**GOOD, "descripcion": "texto\x00con nulo"},
        {**GOOD, "descripcion": "texto\x1bcon escape"},
        {**GOOD, "descripcion": 12345},
        {**GOOD, "descripcion": None},
        {**GOOD, "descripcion": ["a", "b"]},
        {**GOOD, "ticket_id": "TCK-000001"},  # extra field: the id is server generated
        {**GOOD, "estado": "cerrado"},
        {**GOOD, "prioridad": "P1"},  # the client cannot choose the priority
        {**GOOD, "sucursal": ""},
        {**GOOD, "sucursal": "x" * 65},
        {**GOOD, "area": "Caja'; DROP TABLE tickets_nuevos;--"},
        {**GOOD, "sucursal": "Centro' OR '1'='1"},
        {**GOOD, "area": "<script>alert(1)</script>"},
    ],
)
def test_invalid_bodies_are_422_and_never_stored(
    client: TestClient, env: Env, body: dict[str, Any]
) -> None:
    response = _post(client, body)
    assert response.status_code == 422
    assert response.json()["code"] == "validation_error"
    assert env.repo.created == []


def test_description_length_boundaries(client: TestClient, env: Env) -> None:
    assert _post(client, {**GOOD, "descripcion": "a" * 5}).status_code == 201
    assert _post(client, {**GOOD, "descripcion": "a" * 2000}).status_code == 201
    assert _post(client, {**GOOD, "descripcion": "a" * 2001}).status_code == 422
    assert len(env.repo.created) == 2


def test_validation_error_does_not_echo_the_rejected_text(client: TestClient) -> None:
    secret = "MARCA-UNICA-5521"
    response = _post(client, {**GOOD, "descripcion": secret + "\x00"})
    assert response.status_code == 422
    assert secret not in response.text


def test_tab_and_newline_are_allowed_in_the_description(client: TestClient, env: Env) -> None:
    assert _post(client, {**GOOD, "descripcion": "línea uno\nlínea\tdos"}).status_code == 201


def test_sql_injection_in_the_text_fields_is_stored_as_inert_text(
    client: TestClient, env: Env
) -> None:
    payload = "'; DROP TABLE tickets_nuevos; --"
    response = _post(client, {**GOOD, "descripcion": f"La VPN falla {payload}"})
    assert response.status_code == 201
    assert payload in env.repo.created[0].descripcion  # parameterized: kept verbatim


@pytest.mark.parametrize("raw", [b"{", b'{"descripcion": ', b"no json", b"", b"[]", b"null"])
def test_malformed_json_is_422_not_500(client: TestClient, raw: bytes) -> None:
    response = client.post(
        "/tickets", content=raw, headers={**KEY_HEADER, "Content-Type": "application/json"}
    )
    assert response.status_code == 422
    assert response.json()["code"] == "validation_error"


def test_wrong_content_type_is_rejected(client: TestClient, env: Env) -> None:
    response = client.post(
        "/tickets",
        content=b"descripcion=hola",
        headers={**KEY_HEADER, "Content-Type": "text/plain"},
    )
    assert response.status_code == 422
    assert env.repo.created == []


def test_oversized_body_is_413_before_anything_else(client: TestClient, env: Env) -> None:
    big = {**GOOD, "descripcion": "a" * 20_000}
    response = _post(client, big)
    assert response.status_code == 413
    assert response.json()["code"] == "payload_too_large"
    assert env.repo.created == []


def test_413_is_answered_by_the_middleware_even_without_a_key(client: TestClient, env: Env) -> None:
    # The body limit is enforced before routing: no key needed, and the body is not read.
    response = _post(client, {**GOOD, "descripcion": "a" * 20_000}, headers=None)
    assert response.status_code == 413
    assert env.repo.created == []


@pytest.mark.parametrize("method", ["put", "patch", "delete"])
def test_other_methods_on_the_collection_are_405(client: TestClient, method: str) -> None:
    assert getattr(client, method)("/tickets", headers=KEY_HEADER).status_code == 405


def test_database_failure_is_503_without_trace_or_user_text(
    client: TestClient, env: Env, caplog: pytest.LogCaptureFixture
) -> None:
    env.repo.error = RepositoryUnavailableError("sqlite")
    secret = "MARCA-UNICA-7702"
    with caplog.at_level(logging.DEBUG):
        response = _post(client, {**GOOD, "descripcion": f"La VPN falla {secret}"})
    assert response.status_code == 503
    body = response.json()
    assert body["code"] == "database_unavailable"
    assert secret not in response.text
    assert "Traceback" not in response.text
    assert "sqlite" not in response.text.lower()
    logged = _logs(caplog)
    assert secret not in logged
    assert "Traceback" not in logged


def test_unexpected_failure_is_a_generic_500(client: TestClient, env: Env) -> None:
    env.repo.error = RuntimeError("boom with /secret/path")
    response = _post(client, GOOD)
    assert response.status_code == 500
    assert "boom" not in response.text
    assert "/secret/path" not in response.text


def test_sensitive_data_is_flagged_and_absent_from_logs_and_response(
    client: TestClient, env: Env, caplog: pytest.LogCaptureFixture
) -> None:
    with caplog.at_level(logging.DEBUG):
        response = _post(client, {**GOOD, "descripcion": "No entro, mi contraseña es Zx9secretoPW"})
    assert response.status_code == 201
    assert response.json()["sensitive_data_warning"] is True
    assert "Zx9secretoPW" not in response.text
    assert "Zx9secretoPW" not in _logs(caplog)
    assert "Zx9secretoPW" not in env.repo.created[0].descripcion


def test_access_log_has_no_body_or_key(
    client: TestClient, caplog: pytest.LogCaptureFixture
) -> None:
    with caplog.at_level(logging.DEBUG):
        _post(client, {**GOOD, "descripcion": "La VPN falla MARCA-UNICA-1188"})
    logged = _logs(caplog)
    assert "MARCA-UNICA-1188" not in logged
    assert KEY_HEADER["X-API-Key"] not in logged


def test_slow_creation_is_504(
    env: Env, make_client: Callable[[Env], TestClient], monkeypatch: pytest.MonkeyPatch
) -> None:
    import time

    original = env.repo.create_ticket

    def slow(ticket: Any) -> str:
        time.sleep(0.5)
        return original(ticket)

    monkeypatch.setattr(env.repo, "create_ticket", slow)
    env.settings = env.settings.model_copy(
        update={"api": env.settings.api.model_copy(update={"request_timeout_s": 0.1})}
    )
    assert _post(make_client(env), GOOD).status_code == 504
