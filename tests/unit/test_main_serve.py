"""``main.py serve``: fail fast on invalid config or API key, wire uvicorn safely (S8, S17)."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
import uvicorn

import main
import src.api
from src.utils.config import ConfigError, Settings
from src.utils.logging import shutdown_logging
from tests.unit.conftest import API_KEY, settings_with_key


@pytest.fixture(autouse=True)
def _clean_logging() -> Iterator[None]:
    yield
    shutdown_logging()


def _patch_settings(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, key: str | None) -> Settings:
    base = settings_with_key(tmp_path, key=key)
    paths = base.paths.model_copy(update={"logs": tmp_path / "logs"})
    settings = base.model_copy(update={"paths": paths})
    monkeypatch.setattr(main, "load_settings", lambda: settings)
    return settings


@pytest.fixture
def forbid_server(monkeypatch: pytest.MonkeyPatch) -> list[object]:
    """uvicorn and create_app must not run when the config is wrong."""
    started: list[object] = []
    monkeypatch.setattr(uvicorn, "run", lambda *a, **k: started.append((a, k)))
    monkeypatch.setattr(src.api, "create_app", lambda *a, **k: started.append("app"))
    return started


def test_serve_exits_1_when_the_config_is_invalid(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], forbid_server: list[object]
) -> None:
    def broken() -> Settings:
        raise ConfigError("Invalid configuration in config.yaml:\n  - api.port: bad")

    monkeypatch.setattr(main, "load_settings", broken)
    assert main.main(["serve"]) == main.EXIT_CONFIG_ERROR == 1
    err = capsys.readouterr().err
    assert err.startswith("serve: ")
    assert "api.port" in err
    assert forbid_server == []


def test_serve_exits_1_without_an_api_key(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    forbid_server: list[object],
) -> None:
    _patch_settings(monkeypatch, tmp_path, key=None)
    assert main.main(["serve"]) == 1
    assert "DESKPILOT_API_KEY is required" in capsys.readouterr().err
    assert forbid_server == []


def test_serve_exits_1_with_a_short_key_and_does_not_print_it(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    forbid_server: list[object],
) -> None:
    _patch_settings(monkeypatch, tmp_path, key="short-key-1")
    assert main.main(["serve"]) == 1
    captured = capsys.readouterr()
    assert "at least 16 characters" in captured.err
    assert "short-key-1" not in captured.err + captured.out
    assert forbid_server == []


def test_serve_starts_uvicorn_with_safe_options(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    settings = _patch_settings(monkeypatch, tmp_path, key=API_KEY)
    built: list[Settings] = []
    marker = object()
    monkeypatch.setattr(src.api, "create_app", lambda s: built.append(s) or marker)
    calls: list[tuple[tuple[Any, ...], dict[str, Any]]] = []
    monkeypatch.setattr(uvicorn, "run", lambda *a, **k: calls.append((a, k)))

    assert main.main(["serve"]) == main.EXIT_OK
    assert built == [settings]
    ((args, kwargs),) = calls
    assert args == (marker,)
    assert kwargs["host"] == settings.api.host == "127.0.0.1"
    assert kwargs["port"] == settings.api.port
    assert kwargs["access_log"] is False  # the access log would print the query string
    assert kwargs["log_config"] is None
    assert kwargs["server_header"] is False
    captured = capsys.readouterr()
    assert API_KEY not in captured.out + captured.err


def test_serve_cli_overrides_host_and_port(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _patch_settings(monkeypatch, tmp_path, key=API_KEY)
    monkeypatch.setattr(src.api, "create_app", lambda s: object())
    calls: list[dict[str, Any]] = []
    monkeypatch.setattr(uvicorn, "run", lambda *a, **k: calls.append(k))
    assert main.main(["serve", "--host", "0.0.0.0", "--port", "9001"]) == 0
    assert (calls[0]["host"], calls[0]["port"]) == ("0.0.0.0", 9001)


@pytest.mark.parametrize("port", ["0", "-1", "abc"])
def test_serve_rejects_invalid_port(port: str) -> None:
    with pytest.raises(SystemExit) as info:
        main.main(["serve", "--port", port])
    assert info.value.code == 2


def test_serve_never_writes_the_key_to_the_log_file(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    import logging

    _patch_settings(monkeypatch, tmp_path, key=API_KEY)
    monkeypatch.setattr(src.api, "create_app", lambda s: object())

    def run(*_a: Any, **_k: Any) -> None:
        logging.getLogger("src.test").error("starting with key %s", API_KEY)

    monkeypatch.setattr(uvicorn, "run", run)
    assert main.main(["serve"]) == 0
    shutdown_logging()
    logged = (tmp_path / "logs").glob("*.log")
    text = "".join(p.read_text(encoding="utf-8") for p in logged)
    assert "starting with key" in text
    assert API_KEY not in text
