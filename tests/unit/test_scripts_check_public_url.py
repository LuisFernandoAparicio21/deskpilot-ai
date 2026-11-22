"""Behavior tests for scripts/check_public_url.py (S18, T25) over httpx.MockTransport.

No real network: the script's ``httpx.Client`` is replaced by one bound to a fake server.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import httpx
import pytest

from scripts import check_public_url
from scripts.check_public_url import OPENAPI_PATH, Report

API_KEY = "sk-test-very-secret-key-424242"
URL = "https://abc-8000.use.devtunnels.ms"
Handler = Callable[[httpx.Request], httpx.Response]
Override = Callable[[httpx.Request], httpx.Response | None]
RealClient = httpx.Client


def _good_server(request: httpx.Request) -> httpx.Response:
    path = request.url.path
    if path == "/health":
        return httpx.Response(200, json={"status": "ok"})
    if path == "/buscar_solucion":
        if request.headers.get("X-API-Key") != API_KEY:
            return httpx.Response(401, json={"detail": "unauthorized"})
        return httpx.Response(200, json={"status": "ok", "citations": [{"source": "KB-01"}]})
    return httpx.Response(404, json={"detail": "Not Found"})


def _install(
    monkeypatch: pytest.MonkeyPatch, override: Override | None = None
) -> list[httpx.Request]:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        if override is not None and (response := override(request)) is not None:
            return response
        return _good_server(request)

    class MockClient(RealClient):
        def __init__(self, **kwargs: Any) -> None:
            super().__init__(transport=httpx.MockTransport(handler), **kwargs)

    monkeypatch.setattr(httpx, "Client", MockClient)
    return seen


@pytest.fixture(autouse=True)
def _env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(check_public_url, "DEFAULT_ENV_FILE", tmp_path / "no.env")
    monkeypatch.setenv("DESKPILOT_API_KEY", API_KEY)


def _run(*args: str) -> int:
    return check_public_url.main([*args])


def _no_leak(capsys: pytest.CaptureFixture[str]) -> str:
    captured = capsys.readouterr()
    text = captured.out + captured.err
    assert API_KEY not in text
    assert "Traceback" not in text
    return text


def test_https_all_checks_pass_exit_0(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    seen = _install(monkeypatch)
    assert _run(URL) == check_public_url.EXIT_OK == 0
    text = _no_leak(capsys)
    assert "URL uses https" in text
    assert "0 failed" in text
    searches = [r for r in seen if r.url.path == "/buscar_solucion"]
    assert len(searches) == 3  # no key, es, en
    keyed = [r for r in searches if r.headers.get("X-API-Key")]
    assert len(keyed) == 2
    langs = {json.loads(r.content)["query"] for r in keyed}
    assert langs == set(check_public_url.QUERIES.values())
    assert {r.url.path for r in seen} >= {"/health", "/docs", "/redoc", "/openapi.json"}


def test_trailing_slash_in_url_is_accepted(monkeypatch: pytest.MonkeyPatch) -> None:
    _install(monkeypatch)
    assert _run(URL + "/") == 0


def test_http_without_allow_http_exits_1_and_sends_nothing(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    seen = _install(monkeypatch)
    assert _run("http://localhost:8000") == check_public_url.EXIT_CHECK_FAILED == 1
    text = _no_leak(capsys)
    assert "https is required" in text and "--allow-http" in text
    assert seen == []


def test_http_with_allow_http_passes_with_warning(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    _install(monkeypatch)
    assert _run("http://localhost:8000", "--allow-http") == 0
    text = _no_leak(capsys)
    assert "URL uses http (--allow-http)" in text


def test_open_search_without_key_fails(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    def override(request: httpx.Request) -> httpx.Response | None:
        if request.url.path == "/buscar_solucion" and "X-API-Key" not in request.headers:
            return httpx.Response(200, json={"citations": [{"source": "x"}]})
        return None

    _install(monkeypatch, override)
    assert _run(URL) == 1
    assert "without a key -> 200, expected 401" in _no_leak(capsys)


def test_rejected_key_fails(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    def override(request: httpx.Request) -> httpx.Response | None:
        if request.url.path == "/buscar_solucion":
            return httpx.Response(401)
        return None

    _install(monkeypatch, override)
    assert _run(URL) == 1
    assert "the key was rejected" in _no_leak(capsys)


def test_search_200_without_citations_fails(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    def override(request: httpx.Request) -> httpx.Response | None:
        if request.headers.get("X-API-Key"):
            return httpx.Response(200, json={"status": "sin_resultados", "citations": []})
        return None

    _install(monkeypatch, override)
    assert _run(URL) == 1
    assert "200 without citations" in _no_leak(capsys)


def test_health_not_200_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    _install(monkeypatch, lambda r: httpx.Response(502) if r.url.path == "/health" else None)
    assert _run(URL) == 1


@pytest.mark.parametrize("path", ["/docs", "/redoc", "/openapi.json"])
def test_exposed_docs_fail(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], path: str
) -> None:
    _install(
        monkeypatch, lambda r: httpx.Response(200, text="<html>") if r.url.path == path else None
    )
    assert _run(URL) == 1
    assert f"GET {path} -> 200, expected 404" in _no_leak(capsys)


@pytest.mark.parametrize("path", ["/health", "/buscar_solucion"])
def test_timeout_is_a_failure_not_a_crash(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], path: str
) -> None:
    def override(request: httpx.Request) -> httpx.Response | None:
        if request.url.path == path:
            raise httpx.ReadTimeout("slow", request=request)
        return None

    _install(monkeypatch, override)
    assert _run(URL, "--timeout", "2") == 1
    text = _no_leak(capsys)
    assert "timed out after 2.0s" in text


def test_connection_error_hides_url_and_exits_1(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    def override(request: httpx.Request) -> httpx.Response | None:
        raise httpx.ConnectError(f"refused {request.url} {API_KEY}", request=request)

    _install(monkeypatch, override)
    assert _run(URL) == 1
    text = _no_leak(capsys)
    assert "connection error (ConnectError)" in text
    assert "refused" not in text


def test_host_mismatch_with_openapi_is_a_warning_not_a_failure(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    _install(monkeypatch)
    host = json.loads(OPENAPI_PATH.read_text(encoding="utf-8"))["host"]
    assert host != "abc-8000.use.devtunnels.ms"
    assert _run(URL) == 0
    text = _no_leak(capsys)
    assert "openapi.json host is" in text
    assert "export-openapi --host abc-8000.use.devtunnels.ms" in text
    assert "1 warning(s)" in text


def test_matching_openapi_host_is_ok(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    _install(monkeypatch)
    host = json.loads(OPENAPI_PATH.read_text(encoding="utf-8"))["host"]
    assert _run(f"https://{host}") == 0
    text = _no_leak(capsys)
    assert f"openapi.json host matches ({host})" in text
    assert "0 warning(s)" in text


def test_check_openapi_host_unreadable_file_warns(tmp_path: Path) -> None:
    report = Report()
    check_public_url.check_openapi_host(URL, report, tmp_path / "missing.json")
    assert (report.warnings, report.failures) == (1, 0)
    bad = tmp_path / "bad.json"
    bad.write_text("{not json", encoding="utf-8")
    check_public_url.check_openapi_host(URL, report, bad)
    assert (report.warnings, report.failures) == (2, 0)


def test_check_openapi_host_match_and_mismatch(tmp_path: Path) -> None:
    spec = tmp_path / "openapi.json"
    spec.write_text(json.dumps({"host": "abc-8000.use.devtunnels.ms"}), encoding="utf-8")
    report = Report()
    check_public_url.check_openapi_host(URL, report, spec)
    assert (report.warnings, report.failures) == (0, 0)
    check_public_url.check_openapi_host("https://other.example.com", report, spec)
    assert (report.warnings, report.failures) == (1, 0)


def test_slow_response_only_warns(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    _install(monkeypatch)
    assert _run(URL, "--max-latency-ms", "-1") == 0
    text = _no_leak(capsys)
    assert "latency:" in text and "over -1 ms" in text


def test_missing_api_key_variable_exits_2_without_requests(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    seen = _install(monkeypatch)
    monkeypatch.delenv("DESKPILOT_API_KEY")
    assert _run(URL) == check_public_url.EXIT_USAGE == 2
    text = _no_leak(capsys)
    assert "DESKPILOT_API_KEY is not set" in text
    assert seen == []


def test_custom_key_variable_name(monkeypatch: pytest.MonkeyPatch) -> None:
    _install(monkeypatch)
    monkeypatch.delenv("DESKPILOT_API_KEY")
    monkeypatch.setenv("MY_KEY", API_KEY)
    assert _run(URL, "--api-key-env", "MY_KEY") == 0
    assert _run(URL, "--api-key-env", "OTHER_KEY") == 2


def test_key_read_from_env_file(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _install(monkeypatch)
    monkeypatch.delenv("DESKPILOT_API_KEY")
    env_file = tmp_path / "keys.env"
    env_file.write_text(f"DESKPILOT_API_KEY={API_KEY}\n", encoding="utf-8")
    monkeypatch.setattr(check_public_url, "DEFAULT_ENV_FILE", env_file)
    assert _run(URL) == 0


@pytest.mark.parametrize("bad", ["not a url", "ftp://host.example.com", "https://", "/health"])
def test_invalid_url_exits_2(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], bad: str
) -> None:
    seen = _install(monkeypatch)
    assert _run(bad) == 2
    assert "is not a valid URL" in _no_leak(capsys)
    assert seen == []


def test_api_key_never_printed_even_when_server_echoes_it(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    def override(request: httpx.Request) -> httpx.Response | None:
        if request.headers.get("X-API-Key"):
            return httpx.Response(500, text=f"boom key={API_KEY}")
        return None

    _install(monkeypatch, override)
    assert _run(URL) == 1
    _no_leak(capsys)
