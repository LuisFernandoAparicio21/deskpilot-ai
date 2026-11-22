"""``/health`` (RF-26), app wiring and fail-fast key checks (S8, S17)."""

from __future__ import annotations

import logging
from collections.abc import Callable
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from src.api import app as app_module
from src.api import create_app
from src.utils.config import ConfigError
from src.vectordb.chroma_store import IndexNotFoundError
from tests.unit.conftest import KEY_HEADER, Env, settings_with_key


def test_health_ok(client: TestClient, env: Env) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "mode": "local",
        "database": {"status": "ok"},
        "index": {"status": "ok"},
        "index_version": "v-test",
    }


def test_health_degraded_when_the_database_is_down(client: TestClient, env: Env) -> None:
    env.repo.ping_ok = False
    body = client.get("/health").json()
    assert body["status"] == "degraded"
    assert body["database"] == {"status": "unavailable"}
    assert body["index"] == {"status": "ok"}


def test_health_degraded_when_the_index_is_missing(client: TestClient, env: Env) -> None:
    env.probe.error = IndexNotFoundError("run index first")
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "degraded"
    assert body["index"] == {"status": "unavailable"}
    assert body["index_version"] is None
    assert body["database"] == {"status": "ok"}


def test_health_degraded_not_500_when_the_probe_crashes(
    client: TestClient, env: Env, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.DEBUG)
    env.probe.error = RuntimeError("chroma exploded at C:/secret/path")
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "degraded"
    assert "secret" not in response.text
    assert "secret" not in "".join(
        r.getMessage() + str(r.__dict__) for r in caplog.records if r.name.startswith("src")
    )


def test_health_both_down(client: TestClient, env: Env) -> None:
    env.repo.ping_ok = False
    env.probe.error = IndexNotFoundError("x")
    body = client.get("/health").json()
    assert (body["status"], body["database"]["status"], body["index"]["status"]) == (
        "degraded", "unavailable", "unavailable",
    )  # fmt: skip


def test_health_reports_fabric_mode(
    tmp_path: Path, make_client: Callable[[Env], TestClient]
) -> None:
    env = Env(settings_with_key(tmp_path))
    services = env.services()
    services.mode = "fabric"
    client = TestClient(create_app(env.settings, services))
    assert client.get("/health").json()["mode"] == "fabric"


def test_health_is_cached_so_anonymous_calls_do_not_hit_the_database(
    client: TestClient, env: Env
) -> None:
    for _ in range(5):
        assert client.get("/health").status_code == 200
    assert env.repo.pings == 1
    assert env.probe.calls == 1


def test_health_recovers_after_the_cache_expires(
    client: TestClient, env: Env, monkeypatch: pytest.MonkeyPatch
) -> None:
    env.repo.ping_ok = False
    assert client.get("/health").json()["status"] == "degraded"
    env.repo.ping_ok = True
    now = app_module.time.monotonic()
    monkeypatch.setattr(app_module.time, "monotonic", lambda: now + app_module.HEALTH_CACHE_S + 1)
    assert client.get("/health").json()["status"] == "ok"


def test_health_works_with_key_too_and_has_request_id(client: TestClient) -> None:
    response = client.get("/health", headers=KEY_HEADER)
    assert response.status_code == 200
    assert response.headers["X-Request-ID"]


def test_docs_and_openapi_are_not_served(client: TestClient) -> None:
    for path in ("/docs", "/redoc", "/openapi.json"):
        assert client.get(path).status_code == 404
        assert client.get(path, headers=KEY_HEADER).status_code == 404


def test_openapi_spec_is_available_in_code_and_protects_the_tools(client: TestClient) -> None:
    spec = client.app.openapi()  # type: ignore[attr-defined]
    operations = {
        op["operationId"]: (path, method)
        for path, item in spec["paths"].items()
        for method, op in item.items()
    }
    assert set(operations) == {
        "health",
        "buscar_solucion",
        "consultar_estado_ticket",
        "metricas_area",
    }
    assert "security" not in spec["paths"]["/health"]["get"]
    for path, method in (
        ("/buscar_solucion", "post"), ("/tickets/{ticket_id}", "get"), ("/metricas", "get"),
    ):  # fmt: skip
        operation = spec["paths"][path][method]
        assert operation["security"] == [{"APIKeyHeader": []}]
        assert {"401", "422", "500", "503", "504"} <= set(operation["responses"])


@pytest.mark.parametrize("key", [None, "", "k" * 15])
def test_create_app_fails_fast_without_a_usable_key(tmp_path: Path, key: str | None) -> None:
    env = Env(settings_with_key(tmp_path, key=key))
    with pytest.raises(ConfigError, match="DESKPILOT_API_KEY"):
        create_app(env.settings, env.services())


def test_create_app_accepts_a_16_char_key(tmp_path: Path) -> None:
    env = Env(settings_with_key(tmp_path, key="k" * 16))
    client = TestClient(create_app(env.settings, env.services()))
    assert client.get("/tickets/TCK-000001", headers={"X-API-Key": "k" * 16}).status_code == 200


def test_services_are_closed_on_shutdown(env: Env) -> None:
    with TestClient(create_app(env.settings, env.services())) as client:
        assert client.get("/health").status_code == 200
        assert env.closed == 0
    assert env.closed == 1


def test_services_are_swappable_by_injection(tmp_path: Path) -> None:
    """Two apps with different fakes answer differently: no module-level state."""
    first, second = Env(settings_with_key(tmp_path)), Env(settings_with_key(tmp_path))
    second.repo.ping_ok = False
    one = TestClient(create_app(first.settings, first.services()))
    two = TestClient(create_app(second.settings, second.services()))
    assert one.get("/health").json()["status"] == "ok"
    assert two.get("/health").json()["status"] == "degraded"
