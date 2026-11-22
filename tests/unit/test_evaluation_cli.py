"""Unit tests: ``main.py eval`` exit codes and the HTTP backend (T21, RNF-02)."""

from __future__ import annotations

import json
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import NoReturn

import httpx
import pytest

import main
from src.api import evaluation as ev
from src.api.evaluation import (
    EvalError,
    run_cases,
)
from src.utils.config import ConfigError, Settings, load_settings
from src.utils.logging import shutdown_logging
from tests.unit.evalkit import (
    API_KEY,
    API_URL,
    FakeBackend,
    Handler,
    _case,
    _clock,
    _search,
    _write_cases,
)

# --- run_eval / CLI exit codes --------------------------------------------------------


@pytest.fixture
def settings(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Settings]:
    loaded = load_settings(env_file=tmp_path / "missing.env")
    monkeypatch.setattr(main, "load_settings", lambda: loaded)
    yield loaded
    shutdown_logging()


def _patch_backend(monkeypatch: pytest.MonkeyPatch, backend: FakeBackend) -> None:
    @contextmanager
    def fake_open(*args: object, **kwargs: object) -> Iterator[FakeBackend]:
        try:
            yield backend
        finally:
            backend.close()

    monkeypatch.setattr(ev, "open_backend", fake_open)


def _cases_file(tmp_path: Path) -> Path:
    return _write_cases(
        tmp_path / "cases.csv",
        [("A1", "VPN", "i", "articulo:KB-004"), ("R1", "chiste", "i", "rechazo")],
    )


def _argv(tmp_path: Path, *extra: str) -> list[str]:
    cases, out = tmp_path / "cases.csv", tmp_path / "res.csv"
    return ["eval", "--cases", str(cases), "--out", str(out), *extra]


def test_cli_exit_0_when_every_threshold_is_met(
    settings: Settings,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _cases_file(tmp_path)
    backend = FakeBackend(
        lambda q: _search("no_evidence" if q == "chiste" else "answered", ["KB-004"])
    )
    _patch_backend(monkeypatch, backend)
    assert main.main(_argv(tmp_path)) == 0
    assert backend.closed
    assert (tmp_path / "res.csv").is_file()
    assert (tmp_path / "res.summary.json").is_file()
    assert "thresholds met" in capsys.readouterr().out


def test_cli_exit_1_when_a_threshold_is_not_met(
    settings: Settings,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _cases_file(tmp_path)
    _patch_backend(monkeypatch, FakeBackend(lambda q: _search("answered", ["KB-004"])))
    assert main.main(_argv(tmp_path)) == 1
    out = capsys.readouterr().out
    assert "R1" in out
    assert "NOT met" in out


def test_cli_exit_2_when_out_is_the_cases_file(
    settings: Settings, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    cases = _cases_file(tmp_path)
    before = cases.read_bytes()
    assert main.main(["eval", "--cases", str(cases), "--out", str(cases)]) == 2
    assert "--out must not be the cases file" in capsys.readouterr().err
    assert cases.read_bytes() == before  # the input is never overwritten


def test_out_equal_to_cases_is_detected_through_path_aliases(
    settings: Settings, tmp_path: Path
) -> None:
    cases = _cases_file(tmp_path)
    (tmp_path / "sub").mkdir()
    with pytest.raises(EvalError, match="--out must not be the cases file"):
        ev.run_eval(settings, cases, tmp_path / "sub" / ".." / "cases.csv")


def test_cli_exit_2_for_a_bad_cases_file(
    settings: Settings, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    bad = tmp_path / "bad.csv"
    bad.write_text("id,pregunta\n", encoding="utf-8")
    assert main.main(["eval", "--cases", str(bad), "--out", str(tmp_path / "o.csv")]) == 2
    assert "lacks the columns" in capsys.readouterr().err
    assert not (tmp_path / "o.csv").exists()


def test_cli_exit_2_when_the_backend_cannot_start(
    settings: Settings,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _cases_file(tmp_path)

    def broken(*args: object, **kwargs: object) -> NoReturn:
        raise EvalError("no vector index; run: python main.py index")

    monkeypatch.setattr(ev, "open_backend", broken)
    assert main.main(_argv(tmp_path)) == 2
    assert "no vector index" in capsys.readouterr().err


def test_cli_exit_2_on_config_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    def broken() -> Settings:
        raise ConfigError("config.yaml invalido")

    monkeypatch.setattr(main, "load_settings", broken)
    assert main.main(_argv(tmp_path)) == 2
    assert "config.yaml invalido" in capsys.readouterr().err


def test_local_backend_without_database_is_an_error_not_a_crash(
    settings: Settings, tmp_path: Path
) -> None:
    paths = settings.paths.model_copy(update={"sqlite_db": tmp_path / "missing.db"})
    with (
        pytest.raises(EvalError, match="database not found"),
        ev.open_backend(settings.model_copy(update={"paths": paths})),
    ):
        pass


# --- HTTP backend ---------------------------------------------------------------------


def _mock_http(monkeypatch: pytest.MonkeyPatch, handler: Handler) -> None:
    real = httpx.Client

    def factory(**kwargs: object) -> httpx.Client:
        return real(transport=httpx.MockTransport(handler), **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(httpx, "Client", factory)


def _ok_handler(request: httpx.Request) -> httpx.Response:
    if request.url.path == "/buscar_solucion":
        return httpx.Response(
            200,
            json={
                "status": "answered",
                "text": "pasos",
                "citations": [{"article_id": "KB-004"}],
                "sensitive_data_warning": False,
            },
        )
    return httpx.Response(
        201,
        json={
            "categoria": "Accesos",
            "subcategoria": "x",
            "prioridad": "P2",
            "escalado": False,
            "sensitive_data_warning": False,
        },
    )


def test_http_401_aborts_the_run_with_exit_2_and_never_prints_the_key(
    settings: Settings,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _cases_file(tmp_path)
    _mock_http(monkeypatch, lambda request: httpx.Response(401, json={"code": "unauthorized"}))
    code = main.main(_argv(tmp_path, "--api-url", API_URL, "--api-key", API_KEY))
    captured = capsys.readouterr()
    assert code == 2
    assert "rejected the key" in captured.err
    assert API_KEY not in captured.out + captured.err
    assert not (tmp_path / "res.csv").exists()


def test_http_403_is_also_a_key_problem(
    settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    _mock_http(monkeypatch, lambda request: httpx.Response(403))
    with ev.open_backend(settings, API_URL, API_KEY) as backend, pytest.raises(EvalError):
        backend.search("hola")


def test_http_5xx_fails_only_that_case(settings: Settings, monkeypatch: pytest.MonkeyPatch) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if b"falla" in request.content:
            return httpx.Response(503, json={"code": "index_unavailable"})
        return _ok_handler(request)

    _mock_http(monkeypatch, handler)
    cases = [
        _case("A", "articulo:KB-004", "falla"),
        _case("B", "articulo:KB-004", "VPN no conecta"),
        _case("C", "ticket:prioridad=P2", "falla"),
    ]
    with ev.open_backend(settings, API_URL, API_KEY) as backend:
        report = run_cases(cases, backend, "http", _clock())
    assert [r.passed for r in report.results] == [False, True, False]
    assert report.results[0].notas == "http 503"


def test_http_sends_the_api_key_header_and_the_ticket_payload(
    settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return _ok_handler(request)

    _mock_http(monkeypatch, handler)
    with ev.open_backend(settings, API_URL + "/", API_KEY) as backend:
        backend.search("VPN")
        backend.create_ticket("No puedo entrar")
    assert all(r.headers["X-API-Key"] == API_KEY for r in seen)
    assert [r.url.path for r in seen] == ["/buscar_solucion", "/tickets"]
    body = json.loads(seen[1].content)
    assert body["descripcion"] == "No puedo entrar"
    assert {"sucursal", "area", "canal"} <= set(body)


def test_http_top3_is_the_cited_article_and_persistence_is_invisible(
    settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    _mock_http(monkeypatch, _ok_handler)
    with ev.open_backend(settings, API_URL, API_KEY) as backend:
        assert backend.search("VPN").top3 == ["KB-004"]
        assert backend.create_ticket("x").persisted_text is None
        assert backend.logs_since_last_call() is None


@pytest.mark.parametrize(
    "response",
    [
        httpx.Response(200, text="not json"),
        httpx.Response(200, json=["list"]),
        httpx.Response(200, json={"status": "answered"}),
        httpx.Response(404),
    ],
)
def test_http_malformed_responses_fail_the_case_not_the_run(
    settings: Settings, monkeypatch: pytest.MonkeyPatch, response: httpx.Response
) -> None:
    _mock_http(monkeypatch, lambda request: response)
    with ev.open_backend(settings, API_URL, API_KEY) as backend:
        report = run_cases([_case("A", "rechazo")], backend, "http", _clock())
    assert not report.results[0].passed
    assert report.results[0].obtenido == "error"


def test_http_unreachable_server_is_exit_2(
    settings: Settings,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    def refuse(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("refused")

    _cases_file(tmp_path)
    _mock_http(monkeypatch, refuse)
    assert main.main(_argv(tmp_path, "--api-url", API_URL, "--api-key", API_KEY)) == 2
    assert "unreachable" in capsys.readouterr().err


@pytest.mark.parametrize("url", ["localhost:8000", "ftp://x"])
def test_api_url_needs_a_scheme(settings: Settings, url: str) -> None:
    with pytest.raises(EvalError, match="http:// or https://"), ev.open_backend(settings, url, "k"):
        pass


def test_api_key_is_required_for_http(settings: Settings, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DESKPILOT_API_KEY", raising=False)
    no_key = settings.model_copy(
        update={"secrets": settings.secrets.model_copy(update={"api_key": None})}
    )
    with pytest.raises(EvalError), ev.open_backend(no_key, API_URL):
        pass
    with pytest.raises(EvalError, match="empty"), ev.open_backend(no_key, API_URL, ""):
        pass


# --- warning that HTTP mode creates real tickets -------------------------------------------

REAL_TICKETS_WARNING = "HTTP mode creates real tickets on the server"


def _run_with_fake_backend(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, *extra: str) -> int:
    _cases_file(tmp_path)
    _patch_backend(
        monkeypatch,
        FakeBackend(lambda q: _search("no_evidence" if q == "chiste" else "answered", ["KB-004"])),
    )
    return main.main(_argv(tmp_path, *extra))


def test_cli_warns_on_stderr_that_http_mode_creates_real_tickets(
    settings: Settings,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    code = _run_with_fake_backend(tmp_path, monkeypatch, "--api-url", API_URL, "--api-key", API_KEY)
    captured = capsys.readouterr()
    assert code == 0
    assert REAL_TICKETS_WARNING in captured.err
    assert REAL_TICKETS_WARNING not in captured.out
    assert API_KEY not in captured.out + captured.err


def test_cli_local_mode_prints_no_real_tickets_warning(
    settings: Settings,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    code = _run_with_fake_backend(tmp_path, monkeypatch)
    captured = capsys.readouterr()
    assert code == 0
    assert "real tickets" not in captured.out + captured.err
    assert "warning" not in captured.err.lower()
