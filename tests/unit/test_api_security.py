"""API key authentication (RNF-02, S8, S17): 401, ordering against 422, and no key in logs."""

from __future__ import annotations

import json
import logging
from collections.abc import Callable
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from src.api.security import MAX_KEY_BYTES, keys_match
from src.utils.logging import configure_logging, shutdown_logging
from tests.unit.conftest import API_KEY, KEY_HEADER, Env, settings_with_key

PROTECTED = [
    ("POST", "/buscar_solucion", {"json": {"query": "no puedo entrar"}}),
    ("GET", "/tickets/TCK-000001", {}),
    ("GET", "/metricas?area=Caja", {}),
]
ERROR_KEYS = {"code", "message", "request_id", "details"}


@pytest.mark.parametrize(("method", "url", "kwargs"), PROTECTED)
def test_missing_key_is_401(
    client: TestClient, method: str, url: str, kwargs: dict[str, object]
) -> None:
    response = client.request(method, url, **kwargs)  # type: ignore[arg-type]
    assert response.status_code == 401
    body = response.json()
    assert set(body) == ERROR_KEYS
    assert body["code"] == "unauthorized"
    assert response.headers["WWW-Authenticate"] == "X-API-Key"


@pytest.mark.parametrize(
    "bad", ["", "wrong", API_KEY[:-1], API_KEY + "x", API_KEY.upper(), "x" * 1000]
)
@pytest.mark.parametrize(("method", "url", "kwargs"), PROTECTED)
def test_wrong_key_is_401(
    client: TestClient, bad: str, method: str, url: str, kwargs: dict[str, object]
) -> None:
    response = client.request(method, url, headers={"X-API-Key": bad}, **kwargs)  # type: ignore[arg-type]
    assert response.status_code == 401
    assert response.json()["code"] == "unauthorized"


def test_missing_and_wrong_key_give_the_same_body(client: TestClient) -> None:
    missing = client.get("/tickets/TCK-000001")
    wrong = client.get("/tickets/TCK-000001", headers={"X-API-Key": "nope"})
    assert missing.json()["message"] == wrong.json()["message"]
    assert missing.json()["code"] == wrong.json()["code"]


def test_non_ascii_key_is_401_not_500(client: TestClient) -> None:
    response = client.get("/tickets/TCK-000001", headers={b"X-API-Key": "ñandú-ключ".encode()})
    assert response.status_code == 401


def test_other_credentials_do_not_authenticate(client: TestClient) -> None:
    by_bearer = client.get("/tickets/TCK-000001", headers={"Authorization": f"Bearer {API_KEY}"})
    by_query = client.get(f"/tickets/TCK-000001?api_key={API_KEY}")
    assert by_bearer.status_code == 401
    assert by_query.status_code == 401


def test_right_key_passes_and_header_name_is_case_insensitive(client: TestClient) -> None:
    assert client.get("/tickets/TCK-000001", headers=KEY_HEADER).status_code == 200
    assert client.get("/tickets/TCK-000001", headers={"x-api-key": API_KEY}).status_code == 200


def test_health_needs_no_key(client: TestClient) -> None:
    assert client.get("/health").status_code == 200


@pytest.mark.parametrize(
    ("method", "url", "kwargs"),
    [
        ("POST", "/buscar_solucion", {"json": {"query": ""}}),
        ("POST", "/buscar_solucion", {"json": {"query": "x", "extra": 1}}),
        ("POST", "/buscar_solucion", {"content": b"not json"}),
        ("GET", "/tickets/bad%20id", {}),
        ("GET", "/metricas", {}),
        ("GET", "/metricas?area=a&sucursal=b", {}),
    ],
)
def test_401_comes_before_422(
    client: TestClient, env: Env, method: str, url: str, kwargs: dict[str, object]
) -> None:
    unauthenticated = client.request(method, url, **kwargs)  # type: ignore[arg-type]
    authenticated = client.request(method, url, headers=KEY_HEADER, **kwargs)  # type: ignore[arg-type]
    assert authenticated.status_code == 422  # the input really is invalid
    assert unauthenticated.status_code == 401
    assert env.search.calls == []
    assert env.repo.ticket_calls == []


def test_unauthenticated_calls_never_reach_the_services(client: TestClient, env: Env) -> None:
    client.post("/buscar_solucion", json={"query": "hola"})
    client.get("/tickets/TCK-000001")
    client.get("/metricas?area=Caja")
    assert env.search.calls == []
    assert env.repo.ticket_calls == []
    assert env.repo.metric_calls == []


def test_keys_match_rules() -> None:
    assert keys_match(API_KEY, API_KEY)
    assert not keys_match(None, API_KEY)
    assert not keys_match("", API_KEY)
    assert not keys_match(API_KEY[:-1], API_KEY)
    assert not keys_match("ñ" * 10, API_KEY)
    long_key = "k" * MAX_KEY_BYTES
    assert keys_match(long_key, long_key)
    assert not keys_match(long_key + "k", long_key)  # an oversized key never matches


def test_the_key_never_reaches_the_logs(
    tmp_path: Path, make_client: Callable[[Env], TestClient], caplog: pytest.LogCaptureFixture
) -> None:
    """Real JSON log file with redaction on; right, wrong and missing keys, all paths."""
    secret = API_KEY
    wrong = "wrong-key-should-not-be-logged-77"
    env = Env(settings_with_key(tmp_path))
    log_file = configure_logging("DEBUG", tmp_path / "logs", secrets=[secret], console=False)
    assert log_file is not None
    caplog.set_level(logging.DEBUG)
    try:
        client = make_client(env)
        client.get("/tickets/TCK-000001", headers=KEY_HEADER)
        client.get("/tickets/TCK-000001", headers={"X-API-Key": wrong})
        client.get("/tickets/TCK-000001")
        client.get("/metricas?area=Caja", headers={"X-API-Key": secret + "-typo"})
        client.post("/buscar_solucion", json={"query": "x", "bad": 1}, headers=KEY_HEADER)
        env.repo.error = RuntimeError(f"driver failure key={secret}")
        client.get("/tickets/TCK-000009", headers=KEY_HEADER)
    finally:
        shutdown_logging()
    logged = log_file.read_text(encoding="utf-8")
    assert logged.strip(), "the requests must have produced log lines"
    assert secret not in logged
    assert wrong not in logged
    assert secret not in caplog.text
    assert wrong not in caplog.text
    records = [json.loads(line) for line in logged.splitlines()]
    assert all(r["request_id"] for r in records if r["logger"].startswith("src.api"))
    assert any("API key" in r["message"] for r in records)
