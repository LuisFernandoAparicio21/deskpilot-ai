"""``ApiKeyMiddleware`` and ``build_http_app`` of the MCP HTTP transport (S10, RNF-02)."""

from __future__ import annotations

import logging
from pathlib import Path

import pytest
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import PlainTextResponse
from starlette.routing import Route
from starlette.testclient import TestClient
from starlette.types import ASGIApp

from src.api.mcp_server import ApiKeyMiddleware, build_http_app, build_mcp_server
from src.utils.config import ConfigError
from tests.unit.conftest import API_KEY, Env, settings_with_key


def _inner() -> tuple[ASGIApp, list[str]]:
    seen: list[str] = []

    async def endpoint(request: Request) -> PlainTextResponse:
        seen.append(request.url.path)
        return PlainTextResponse("inner-reached")

    return Starlette(routes=[Route("/mcp", endpoint, methods=["GET", "POST"])]), seen


@pytest.fixture
def guarded() -> tuple[TestClient, list[str]]:
    inner, seen = _inner()
    return TestClient(ApiKeyMiddleware(inner, API_KEY)), seen


def test_no_credentials_is_401_and_does_not_reach_the_app(
    guarded: tuple[TestClient, list[str]],
) -> None:
    client, seen = guarded
    response = client.post("/mcp", json={})
    assert response.status_code == 401
    assert response.json() == {"code": "unauthorized", "message": "Missing or invalid API key."}
    assert response.headers["www-authenticate"] == "Bearer, X-API-Key"
    assert seen == []


@pytest.mark.parametrize(
    "headers",
    [
        {"X-API-Key": "wrong"},
        {"X-API-Key": ""},
        {"X-API-Key": API_KEY + "x"},
        {"X-API-Key": API_KEY[:-1]},
        {"X-API-Key": API_KEY.upper()},
        {"Authorization": "Bearer wrong"},
        {"Authorization": "Bearer "},
        {"Authorization": "Bearer"},
        {"Authorization": f"Basic {API_KEY}"},
        {"Authorization": API_KEY},
        {"Authorization": f"Bearer {API_KEY}x"},
        {"X-API-Key": "x" * 5000},
    ],
)
def test_wrong_credentials_are_401(
    guarded: tuple[TestClient, list[str]], headers: dict[str, str]
) -> None:
    client, seen = guarded
    assert client.post("/mcp", json={}, headers=headers).status_code == 401
    assert client.get("/mcp", headers=headers).status_code == 401
    assert seen == []


def test_key_in_query_string_does_not_authenticate(
    guarded: tuple[TestClient, list[str]],
) -> None:
    client, seen = guarded
    assert client.post(f"/mcp?api_key={API_KEY}", json={}).status_code == 401
    assert seen == []


@pytest.mark.parametrize(
    "headers",
    [
        {"X-API-Key": API_KEY},
        {"x-api-key": API_KEY},
        {"Authorization": f"Bearer {API_KEY}"},
        {"Authorization": f"bearer {API_KEY}"},
    ],
)
def test_valid_key_by_header_or_bearer_reaches_the_app(
    guarded: tuple[TestClient, list[str]], headers: dict[str, str]
) -> None:
    client, seen = guarded
    response = client.post("/mcp", json={}, headers=headers)
    assert response.status_code == 200
    assert response.text == "inner-reached"
    assert seen == ["/mcp"]


def test_wrong_x_api_key_wins_over_a_valid_bearer(guarded: tuple[TestClient, list[str]]) -> None:
    """Documents the precedence: when X-API-Key is present it alone is checked."""
    client, seen = guarded
    headers = {"X-API-Key": "wrong", "Authorization": f"Bearer {API_KEY}"}
    assert client.post("/mcp", json={}, headers=headers).status_code == 401
    assert seen == []


def test_non_ascii_key_is_401_not_500(guarded: tuple[TestClient, list[str]]) -> None:
    client, _ = guarded
    response = client.post("/mcp", json={}, headers={"X-API-Key": "ñandú-ключ".encode()})
    assert response.status_code == 401


def test_rejections_are_logged_without_the_keys(
    guarded: tuple[TestClient, list[str]], caplog: pytest.LogCaptureFixture
) -> None:
    client, _ = guarded
    caplog.set_level(logging.DEBUG)
    client.post("/mcp", json={}, headers={"X-API-Key": "attempt-secret-4242"})
    client.post("/mcp", json={}, headers={"Authorization": "Bearer attempt-bearer-4242"})
    dump = "\n".join(f"{r.getMessage()} {r.__dict__}" for r in caplog.records)
    assert "rejected" in dump
    assert "attempt-secret-4242" not in dump
    assert "attempt-bearer-4242" not in dump
    assert API_KEY not in dump


def test_build_http_app_fails_fast_without_a_valid_key(tmp_path: Path) -> None:
    for key in (None, "short"):
        env = Env(settings_with_key(tmp_path, key=key))
        server = build_mcp_server(env.settings, env.services())
        with pytest.raises(ConfigError) as info:
            build_http_app(server, env.settings, "127.0.0.1", "/mcp")
        if key:
            assert key not in str(info.value)


def test_build_http_app_wraps_the_server_with_the_key_guard(env: Env) -> None:
    server = build_mcp_server(env.settings, env.services())
    app = build_http_app(server, env.settings, "127.0.0.1", "/custom")
    assert isinstance(app, ApiKeyMiddleware)
    client = TestClient(app)
    assert client.post("/custom", json={}).status_code == 401
    assert client.post("/mcp", json={}).status_code == 401  # guarded before routing
