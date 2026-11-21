"""Unit tests for the CLI in main.py."""

from __future__ import annotations

import argparse
import csv
from collections.abc import Callable, Iterator
from pathlib import Path

import pytest

import main
from src.utils.config import ConfigError, Settings, load_settings
from src.utils.logging import shutdown_logging

EXPECTED_COMMANDS = {"generate-data", "load-db", "index", "serve", "eval", "export-openapi"}
PLACEHOLDER_COMMANDS = EXPECTED_COMMANDS - set(main.HANDLERS)


def _subcommands(parser: argparse.ArgumentParser) -> set[str]:
    for action in parser._actions:
        if isinstance(action, argparse._SubParsersAction):
            return set(action.choices)
    return set()


def _rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


@pytest.fixture
def tmp_settings(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Settings]:
    """Real config.yaml with every output path redirected to ``tmp_path``."""
    settings = load_settings(env_file=tmp_path / "missing.env")
    paths = settings.paths.model_copy(
        update={"raw": tmp_path / "raw", "sample": tmp_path / "sample", "logs": tmp_path / "logs"}
    )
    patched = settings.model_copy(update={"paths": paths})
    monkeypatch.setattr(main, "load_settings", lambda: patched)
    yield patched
    shutdown_logging()


def test_parser_exposes_the_six_subcommands() -> None:
    assert _subcommands(main.build_parser()) == EXPECTED_COMMANDS


@pytest.mark.parametrize("command", sorted(PLACEHOLDER_COMMANDS))
def test_placeholder_subcommand_exits_with_code_2(
    command: str, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main.main([command]) == main.EXIT_NOT_IMPLEMENTED
    assert "not implemented yet (T" in capsys.readouterr().err


def test_missing_subcommand_is_an_error() -> None:
    with pytest.raises(SystemExit) as excinfo:
        main.main([])
    assert excinfo.value.code == 2


def test_generate_data_writes_the_three_files(
    tmp_settings: Settings, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main.main(["generate-data", "--n", "300", "--seed", "7"]) == main.EXIT_OK
    tickets = _rows(tmp_settings.paths.raw / "tickets.csv")
    assert len(tickets) == 300
    assert len(_rows(tmp_settings.paths.raw / "sucursales.csv")) == 120
    assert len(_rows(tmp_settings.paths.sample / "tickets_sample.csv")) == 200
    out = capsys.readouterr().out
    assert "seed=7" in out
    assert "300 tickets" in out
    assert "repetitive share" in out


def test_generate_data_defaults_come_from_config(
    tmp_settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[tuple[int, int]] = []
    real: Callable[..., object] = main.generate_dataset

    def spy(seed: int, n: int, *args: object) -> object:
        calls.append((seed, n))
        return real(seed, 50, *args)

    monkeypatch.setattr(main, "generate_dataset", spy)
    assert main.main(["generate-data"]) == main.EXIT_OK
    assert calls == [(tmp_settings.data.seed, tmp_settings.data.n_tickets)]


@pytest.mark.parametrize("args", [["--n", "0"], ["--seed", "-1"], ["--n", "abc"]])
def test_generate_data_rejects_invalid_arguments(args: list[str]) -> None:
    with pytest.raises(SystemExit) as excinfo:
        main.main(["generate-data", *args])
    assert excinfo.value.code == 2


def test_generate_data_reports_config_errors(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    def broken() -> Settings:
        raise ConfigError("Configuration file not found: config.yaml")

    monkeypatch.setattr(main, "load_settings", broken)
    assert main.main(["generate-data"]) == main.EXIT_CONFIG_ERROR
    assert "Configuration file not found" in capsys.readouterr().err
