"""``main.py mcp`` and ``McpConfig``: bad config, transports, key never printed (S10)."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

import main
import src.api
import src.api.mcp_server as mcp_server
from src.utils.config import DEFAULT_CONFIG_PATH, ConfigError, McpConfig, Settings, load_settings
from src.utils.logging import shutdown_logging
from tests.unit.conftest import API_KEY, Env, settings_with_key


@pytest.fixture(autouse=True)
def _clean_logging() -> Iterator[None]:
    yield
    shutdown_logging()


class Spy:
    """Replaces build_services/build_mcp_server/run_stdio/run_http and records the calls."""

    def __init__(self, env: Env) -> None:
        self.env = env
        self.events: list[str] = []
        self.http_args: tuple[Any, ...] | None = None
        self.fail_with: Exception | None = None

    def build_services(self, settings: Settings) -> Any:
        self.events.append("services")
        return self.env.services()

    def build_server(self, settings: Settings, services: Any) -> object:
        self.events.append("server")
        return "server"

    def run_stdio(self, server: object) -> None:
        self.events.append("stdio")
        if self.fail_with:
            raise self.fail_with

    def run_http(self, server: object, settings: Settings, host: str, port: int, path: str) -> None:
        self.events.append("http")
        self.http_args = (host, port, path)


@pytest.fixture
def spy(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Spy:
    spy = Spy(Env(settings_with_key(tmp_path)))
    monkeypatch.setattr(src.api, "build_services", spy.build_services)
    monkeypatch.setattr(mcp_server, "build_mcp_server", spy.build_server)
    monkeypatch.setattr(mcp_server, "run_stdio", spy.run_stdio)
    monkeypatch.setattr(mcp_server, "run_http", spy.run_http)
    return spy


def _patch(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, key: str | None, **mcp: Any
) -> Settings:
    base = settings_with_key(tmp_path, key=key)
    paths = base.paths.model_copy(update={"logs": tmp_path / "logs"})
    settings = base.model_copy(update={"paths": paths, "mcp": base.mcp.model_copy(update=mcp)})
    monkeypatch.setattr(main, "load_settings", lambda: settings)
    return settings


def test_mcp_exits_1_on_invalid_config_without_starting_anything(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], spy: Spy
) -> None:
    def broken() -> Settings:
        raise ConfigError("Invalid configuration in config.yaml:\n  - mcp.port: bad")

    monkeypatch.setattr(main, "load_settings", broken)
    assert main.main(["mcp"]) == main.EXIT_CONFIG_ERROR == 1
    err = capsys.readouterr().err
    assert err.startswith("mcp: ")
    assert "mcp.port" in err
    assert spy.events == []


@pytest.mark.parametrize(("key", "fragment"), [(None, "required"), ("short-key-1", "16")])
def test_mcp_http_exits_1_without_a_valid_key_and_never_prints_it(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    spy: Spy,
    key: str | None,
    fragment: str,
) -> None:
    _patch(monkeypatch, tmp_path, key=key)
    assert main.main(["mcp", "--transport", "http"]) == 1
    captured = capsys.readouterr()
    assert fragment in captured.err
    if key:
        assert key not in captured.out + captured.err
    assert spy.events == []


def test_mcp_http_by_config_transport_also_needs_the_key(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, spy: Spy
) -> None:
    _patch(monkeypatch, tmp_path, key=None, transport="http")
    assert main.main(["mcp"]) == 1
    assert spy.events == []


def test_mcp_stdio_is_the_default_needs_no_key_and_closes_services(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, spy: Spy
) -> None:
    _patch(monkeypatch, tmp_path, key=None)
    assert main.main(["mcp"]) == main.EXIT_OK
    assert spy.events == ["services", "server", "stdio"]
    assert spy.env.closed == 1


def test_mcp_closes_services_even_when_the_server_fails(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, spy: Spy
) -> None:
    _patch(monkeypatch, tmp_path, key=None)
    spy.fail_with = RuntimeError("boom")
    with pytest.raises(RuntimeError):
        main.main(["mcp"])
    assert spy.env.closed == 1


def test_mcp_http_uses_config_host_port_path(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str], spy: Spy
) -> None:
    _patch(monkeypatch, tmp_path, key=API_KEY, transport="http", port=8123, path="/x")
    assert main.main(["mcp"]) == 0
    assert spy.events == ["services", "server", "http"]
    assert spy.http_args == ("127.0.0.1", 8123, "/x")
    captured = capsys.readouterr()
    assert API_KEY not in captured.out + captured.err


def test_mcp_cli_overrides_transport_host_and_port(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, spy: Spy
) -> None:
    _patch(monkeypatch, tmp_path, key=API_KEY)
    assert main.main(["mcp", "--transport", "http", "--host", "0.0.0.0", "--port", "9009"]) == 0
    assert spy.http_args == ("0.0.0.0", 9009, "/mcp")


def test_mcp_stdio_flag_overrides_http_config(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, spy: Spy
) -> None:
    _patch(monkeypatch, tmp_path, key=None, transport="http")
    assert main.main(["mcp", "--transport", "stdio"]) == 0
    assert "stdio" in spy.events


@pytest.mark.parametrize(
    "argv", [["--port", "0"], ["--port", "abc"], ["--port", "-3"], ["--transport", "sse"]]
)
def test_mcp_rejects_invalid_arguments(argv: list[str]) -> None:
    with pytest.raises(SystemExit) as info:
        main.main(["mcp", *argv])
    assert info.value.code == 2


def test_mcp_is_a_real_handler() -> None:
    assert "mcp" in main.HANDLERS


# --- McpConfig -------------------------------------------------------------------------------


def test_mcp_config_defaults_are_local_and_stdio() -> None:
    cfg = McpConfig()
    assert (cfg.transport, cfg.host, cfg.port, cfg.path) == ("stdio", "127.0.0.1", 8001, "/mcp")


@pytest.mark.parametrize(
    "bad",
    [
        {"transport": "sse"},
        {"transport": ""},
        {"port": 0},
        {"port": 65536},
        {"port": "x"},
        {"host": ""},
        {"path": "mcp"},
        {"path": "/a b"},
        {"path": "/a?b=1"},
        {"unknown": 1},
    ],
)
def test_mcp_config_rejects_invalid_values(bad: dict[str, Any]) -> None:
    with pytest.raises(ValidationError):
        McpConfig(**bad)


@pytest.mark.parametrize("port", [1, 8001, 65535])
def test_mcp_config_accepts_port_bounds(port: int) -> None:
    assert McpConfig(port=port).port == port


def test_load_settings_reports_an_invalid_mcp_section(tmp_path: Path) -> None:
    text = DEFAULT_CONFIG_PATH.read_text(encoding="utf-8")
    assert "transport: stdio" in text
    bad = tmp_path / "config.yaml"
    bad.write_text(text.replace("transport: stdio", "transport: carrier-pigeon"), encoding="utf-8")
    with pytest.raises(ConfigError) as info:
        load_settings(bad, env_file=tmp_path / "missing.env")
    assert "mcp.transport" in str(info.value)


def test_real_config_yaml_has_a_valid_mcp_section(tmp_path: Path) -> None:
    settings = load_settings(env_file=tmp_path / "missing.env")
    assert settings.mcp == McpConfig()
