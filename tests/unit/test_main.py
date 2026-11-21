"""Unit tests for the CLI skeleton in main.py."""

from __future__ import annotations

import argparse

import pytest

import main

EXPECTED_COMMANDS = {"generate-data", "load-db", "index", "serve", "eval", "export-openapi"}


def _subcommands(parser: argparse.ArgumentParser) -> set[str]:
    for action in parser._actions:
        if isinstance(action, argparse._SubParsersAction):
            return set(action.choices)
    return set()


def test_parser_exposes_the_six_subcommands() -> None:
    assert _subcommands(main.build_parser()) == EXPECTED_COMMANDS


@pytest.mark.parametrize("command", sorted(EXPECTED_COMMANDS))
def test_placeholder_subcommand_exits_with_code_2(
    command: str, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main.main([command]) == main.EXIT_NOT_IMPLEMENTED
    assert "not implemented yet (T" in capsys.readouterr().err


def test_missing_subcommand_is_an_error() -> None:
    with pytest.raises(SystemExit) as excinfo:
        main.main([])
    assert excinfo.value.code == 2
