"""Uniform errors, X-Request-ID, 413/500/503/504 and log hygiene (RNF-05, RNF-06, S8, S17)."""

from __future__ import annotations

import logging
import re
from collections.abc import Callable
from pathlib import Path

import anyio
import pytest
from fastapi.testclient import TestClient

from src.api.repository import RepositoryUnavailableError
from src.vectordb.chroma_store import IndexNotFoundError
from tests.unit.conftest import KEY_HEADER, Env, settings_with_key

ERROR_KEYS = {"code", "message", "request_id", "details"}
GENERATED_ID = re.compile(r"^[0-9a-f]{32}$")
SAFE_ID = "client-req-0001"
MARK = "SECRETMARK-user-text-4711"


def _server_logs(caplog: pytest.LogCaptureFixture) -> str:
    """Everything the API logged (messages and extras), without the test client's own logs."""
    return "\n".join(
        f"{r.name} {r.getMessage()} {r.__dict__}"
        for r in caplog.records
        if r.name.startswith("src")
    )


def _assert_uniform(response, status: int, code: str) -> None:  # type: ignore[no-untyped-def]
    body = response.json()
    assert response.status_code == status
    assert set(body) == ERROR_KEYS
    assert body["code"] == code
    assert isinstance(body["message"], str) and body["message"]
    assert body["request_id"] == response.headers["X-Request-ID"]


def _all_error_responses(client: TestClient, env: Env) -> dict[int, object]:
    """One response per error status the API can produce."""
    responses: dict[int, object] = {}
    responses[401] = client.get("/tickets/TCK-000001")
    responses[404] = client.get("/tickets/NOPE", headers=KEY_HEADER)
    responses[405] = client.delete("/tickets/TCK-000001", headers=KEY_HEADER)
    responses[422] = client.get("/metricas", headers=KEY_HEADER)
    responses[413] = client.post("/buscar_solucion", content=b"x" * 20_000, headers={**KEY_HEADER})
    env.repo.error = RepositoryUnavailableError("sqlite")
    responses[503] = client.get("/tickets/TCK-000001", headers=KEY_HEADER)
    env.repo.error = RuntimeError("boom")
    responses[500] = client.get("/tickets/TCK-000001", headers=KEY_HEADER)
    return responses


def test_every_error_uses_the_uniform_body_and_request_id(client: TestClient, env: Env) -> None:
    responses = _all_error_responses(client, env)
    codes = {
        401: "unauthorized",
        404: "ticket_not_found",
        405: "method_not_allowed",
        422: "validation_error",
        413: "payload_too_large",
        503: "database_unavailable",
        500: "internal_error",
    }
    for status, code in codes.items():
        _assert_uniform(responses[status], status, code)


def test_unknown_route_is_a_uniform_404(client: TestClient) -> None:
    response = client.get("/nope")
    _assert_uniform(response, 404, "not_found")


def test_request_id_header_on_success_and_health(client: TestClient) -> None:
    assert GENERATED_ID.match(client.get("/health").headers["X-Request-ID"])
    ok = client.get("/tickets/TCK-000001", headers=KEY_HEADER)
    assert GENERATED_ID.match(ok.headers["X-Request-ID"])


def test_safe_client_request_id_is_kept_everywhere(client: TestClient, env: Env) -> None:
    headers = {"X-Request-ID": SAFE_ID}
    ok = client.get("/tickets/TCK-000001", headers={**KEY_HEADER, **headers})
    unauthorized = client.get("/tickets/TCK-000001", headers=headers)
    invalid = client.get("/metricas", headers={**KEY_HEADER, **headers})
    assert ok.headers["X-Request-ID"] == SAFE_ID
    assert unauthorized.headers["X-Request-ID"] == SAFE_ID
    assert unauthorized.json()["request_id"] == SAFE_ID
    assert invalid.json()["request_id"] == SAFE_ID
    env.repo.error = RuntimeError("boom")
    failed = client.get("/tickets/TCK-000001", headers={**KEY_HEADER, **headers})
    assert failed.status_code == 500
    assert failed.headers["X-Request-ID"] == SAFE_ID
    assert failed.json()["request_id"] == SAFE_ID


@pytest.mark.parametrize(
    "bad", ["short", "has spaces in it!", "x" * 65, "ñandú-request-id", "a;b<c>d1234"]
)
def test_unsafe_client_request_id_is_replaced(client: TestClient, bad: str) -> None:
    response = client.get("/health", headers={"X-Request-ID": bad.encode()})
    assert response.headers["X-Request-ID"] != bad
    assert GENERATED_ID.match(response.headers["X-Request-ID"])


def test_boundary_lengths_of_request_id(client: TestClient) -> None:
    for ok in ("a" * 8, "a" * 64):
        assert client.get("/health", headers={"X-Request-ID": ok}).headers["X-Request-ID"] == ok


def test_generated_ids_are_unique(client: TestClient) -> None:
    ids = {client.get("/health").headers["X-Request-ID"] for _ in range(5)}
    assert len(ids) == 5


def test_security_headers_on_every_response(client: TestClient, env: Env) -> None:
    for response in (client.get("/health"), client.get("/tickets/X", headers=KEY_HEADER)):
        assert response.headers["Cache-Control"] == "no-store"
        assert response.headers["X-Content-Type-Options"] == "nosniff"


# --- 413 -----------------------------------------------------------------------------


def test_declared_body_over_the_limit_is_413_without_reaching_the_service(
    client: TestClient, env: Env
) -> None:
    limit = env.settings.api.max_body_bytes
    body = b'{"query": "' + b"a" * limit + b'"}'
    response = client.post("/buscar_solucion", content=body, headers=KEY_HEADER)
    _assert_uniform(response, 413, "payload_too_large")
    assert env.search.calls == []


def test_chunked_body_over_the_limit_is_413(client: TestClient, env: Env) -> None:
    limit = env.settings.api.max_body_bytes

    def chunks():  # type: ignore[no-untyped-def]
        for _ in range(4):
            yield b"a" * (limit // 2)

    response = client.post(
        "/buscar_solucion",
        content=chunks(),
        headers={**KEY_HEADER, "Content-Type": "application/json"},
    )
    _assert_uniform(response, 413, "payload_too_large")
    assert env.search.calls == []


def test_body_at_the_limit_is_not_413(client: TestClient, env: Env) -> None:
    limit = env.settings.api.max_body_bytes
    response = client.post(
        "/buscar_solucion",
        content=b"{" + b" " * (limit - 2) + b"}",
        headers={**KEY_HEADER, "Content-Type": "application/json"},
    )
    assert response.status_code == 422  # parsed, then rejected for the missing query


# --- 500 -----------------------------------------------------------------------------


def test_unexpected_error_is_500_without_leaking_text(
    client: TestClient, env: Env, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.DEBUG)
    env.search.error = RuntimeError(f"db password=hunter2 query={MARK}")
    response = client.post(
        "/buscar_solucion", json={"query": f"consulta {MARK}"}, headers=KEY_HEADER
    )
    _assert_uniform(response, 500, "internal_error")
    assert "hunter2" not in response.text
    assert MARK not in response.text
    assert "Traceback" not in response.text
    unhandled = [r for r in caplog.records if r.getMessage() == "Unhandled error"]
    assert len(unhandled) == 1
    assert unhandled[0].__dict__["error"] == "RuntimeError"
    assert unhandled[0].exc_info is None


def test_user_text_never_reaches_the_logs_on_any_path(
    client: TestClient, env: Env, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.DEBUG)
    ok = client.post("/buscar_solucion", json={"query": f"hola {MARK}"}, headers=KEY_HEADER)
    invalid = client.post("/buscar_solucion", json={"query": MARK, "x": MARK}, headers=KEY_HEADER)
    area = client.get("/metricas", params={"area": f"Caja{MARK}'"}, headers=KEY_HEADER)
    ticket_422 = client.get(f"/tickets/{MARK}%20x", headers=KEY_HEADER)
    ticket_404 = client.get(f"/tickets/{MARK[:30]}", headers=KEY_HEADER)
    env.search.error = ValueError(MARK)
    boom = client.post("/buscar_solucion", json={"query": MARK}, headers=KEY_HEADER)
    env.repo.error = RuntimeError(MARK)
    boom_repo = client.get(f"/tickets/{MARK[:30]}", headers=KEY_HEADER)
    statuses = [r.status_code for r in (ok, invalid, area, ticket_422, ticket_404, boom, boom_repo)]
    assert statuses == [200, 422, 422, 422, 404, 500, 500]
    assert MARK not in _server_logs(caplog)
    assert MARK[:30] not in _server_logs(caplog)
    for record in caplog.records:
        assert record.exc_info is None or record.name != "src.api.middleware"


def test_access_log_has_route_status_and_no_query_string(
    client: TestClient, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.INFO)
    client.get(f"/tickets/TCK-000001?note={MARK}", headers=KEY_HEADER)
    handled = [r for r in caplog.records if r.getMessage() == "Request handled"]
    assert len(handled) == 1
    extra = handled[0].__dict__
    assert extra["method"] == "GET"
    assert extra["path"] == "/tickets/{ticket_id}"
    assert extra["status"] == 200
    assert extra["duration_ms"] >= 0
    assert MARK not in _server_logs(caplog)
    assert "TCK-000001" not in _server_logs(caplog)


# --- 503 -----------------------------------------------------------------------------


def test_missing_index_is_503_index_unavailable(client: TestClient, env: Env) -> None:
    env.search.error = IndexNotFoundError("no index at C:/secret/path")
    response = client.post("/buscar_solucion", json={"query": "vpn"}, headers=KEY_HEADER)
    _assert_uniform(response, 503, "index_unavailable")
    assert "secret" not in response.text


@pytest.mark.parametrize(
    ("url", "code"),
    [
        ("/tickets/TCK-000001", "database_unavailable"),
        ("/metricas?area=Caja", "database_unavailable"),
    ],
)
def test_missing_database_is_503(client: TestClient, env: Env, url: str, code: str) -> None:
    env.repo.error = RepositoryUnavailableError("sqlite")
    response = client.get(url, headers=KEY_HEADER)
    _assert_uniform(response, 503, code)


# --- 504 -----------------------------------------------------------------------------


@pytest.mark.parametrize("path", ["search", "ticket", "metrics"])
def test_slow_call_is_504_within_the_timeout(
    tmp_path: Path, make_client: Callable[[Env], TestClient], path: str
) -> None:
    import time

    env = Env(settings_with_key(tmp_path, request_timeout_s=0.2))
    env.search.delay_s = 1.5
    original_ticket, original_metrics = env.repo.get_ticket_status, env.repo.area_metrics

    def slow_ticket(ticket_id):  # type: ignore[no-untyped-def]
        time.sleep(1.5)
        return original_ticket(ticket_id)

    def slow_metrics(scope, name):  # type: ignore[no-untyped-def]
        time.sleep(1.5)
        return original_metrics(scope, name)

    env.repo.get_ticket_status = slow_ticket  # type: ignore[method-assign]
    env.repo.area_metrics = slow_metrics  # type: ignore[method-assign]
    client = make_client(env)
    started = time.perf_counter()
    if path == "search":
        response = client.post("/buscar_solucion", json={"query": "vpn"}, headers=KEY_HEADER)
    elif path == "ticket":
        response = client.get("/tickets/TCK-000001", headers=KEY_HEADER)
    else:
        response = client.get("/metricas?area=Caja", headers=KEY_HEADER)
    elapsed = time.perf_counter() - started
    _assert_uniform(response, 504, "timeout")
    assert elapsed < 1.2  # answered at the timeout, not when the worker finished


def test_fast_call_under_the_timeout_is_not_504(
    tmp_path: Path, make_client: Callable[[Env], TestClient]
) -> None:
    env = Env(settings_with_key(tmp_path, request_timeout_s=2))
    env.search.delay_s = 0.1
    client = make_client(env)
    assert (
        client.post("/buscar_solucion", json={"query": "vpn"}, headers=KEY_HEADER).status_code
        == 200
    )


# --- 404 ticket / metrics --------------------------------------------------------------


def test_unknown_ticket_is_404_without_extra_data_or_echo(client: TestClient) -> None:
    response = client.get("/tickets/TCK-999999", headers=KEY_HEADER)
    _assert_uniform(response, 404, "ticket_not_found")
    assert "TCK-999999" not in response.text


def test_unknown_area_is_404(client: TestClient) -> None:
    response = client.get("/metricas", params={"area": "Inexistente"}, headers=KEY_HEADER)
    _assert_uniform(response, 404, "not_found")
    assert "Inexistente" not in response.text


# --- success shape -----------------------------------------------------------------------


def test_search_response_carries_the_answer_without_echoing_the_query(
    client: TestClient,
) -> None:
    response = client.post("/buscar_solucion", json={"query": MARK}, headers=KEY_HEADER)
    body = response.json()
    assert response.status_code == 200
    assert set(body) == {
        "status",
        "language",
        "text",
        "citations",
        "sensitive_data_warning",
        "mode",
    }
    assert body["citations"][0]["article_id"] == "KB-001"
    assert MARK not in response.text


def test_ticket_response_exposes_only_the_documented_fields(client: TestClient) -> None:
    body = client.get("/tickets/TCK-000001", headers=KEY_HEADER).json()
    assert set(body) == {
        "ticket_id", "estado", "prioridad", "fecha_apertura", "fecha_cierre",
        "sla_horas", "fecha_limite_sla", "sla_cumplido",
    }  # fmt: skip
    assert body["fecha_cierre"] is None and body["sla_cumplido"] is None


def test_request_id_with_a_trailing_newline_is_discarded_and_regenerated(
    client: TestClient,
) -> None:
    """A newline-terminated id must not pass; sent as raw ASGI (HTTP clients refuse the newline)."""
    bad = b"valid-id-0001\n"
    sent: list[dict[str, object]] = []

    async def drive() -> None:
        async def receive() -> dict[str, object]:
            return {"type": "http.request", "body": b"", "more_body": False}

        async def send(message: dict[str, object]) -> None:
            sent.append(message)

        scope = {
            "type": "http",
            "asgi": {"version": "3.0"},
            "http_version": "1.1",
            "method": "GET",
            "scheme": "http",
            "path": "/health",
            "raw_path": b"/health",
            "query_string": b"",
            "headers": [(b"x-request-id", bad)],
            "client": ("testclient", 1),
            "server": ("testserver", 80),
        }
        await client.app(scope, receive, send)  # type: ignore[arg-type]

    anyio.run(drive)
    start = next(m for m in sent if m["type"] == "http.response.start")
    headers = dict(start["headers"])  # type: ignore[call-overload]
    returned = headers[b"x-request-id"].decode()
    assert "\n" not in returned
    assert returned != bad.decode().strip()
    assert GENERATED_ID.match(returned)


def test_body_over_the_limit_is_413_even_without_an_api_key(client: TestClient, env: Env) -> None:
    limit = env.settings.api.max_body_bytes
    response = client.post(
        "/buscar_solucion",
        content=b"a" * (limit + 1),
        headers={"Content-Type": "application/json"},
    )
    assert int(response.request.headers["content-length"]) == limit + 1
    _assert_uniform(response, 413, "payload_too_large")
    assert env.search.calls == []
