"""Unit tests for structured JSON logging with request_id and redaction (RNF-05, RNF-07)."""

from __future__ import annotations

import asyncio
import json
import logging
import re
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from src.utils.config import load_settings
from src.utils.logging import (
    LOG_FILE_NAME,
    configure_logging,
    configure_logging_from_settings,
    get_request_id,
    request_context,
    reset_request_id,
    set_request_id,
    shutdown_logging,
)

API_KEY = "synthetic-api-key-0123456789-abcdef"
FIELDS = {"timestamp", "level", "logger", "message", "request_id", "extra"}


@pytest.fixture(autouse=True)
def _cleanup() -> Iterator[None]:
    yield
    shutdown_logging()


def _lines(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def test_every_line_is_json_with_the_required_fields(tmp_path: Path) -> None:
    log_file = configure_logging("INFO", tmp_path, console=False)
    assert log_file == tmp_path / LOG_FILE_NAME
    log = logging.getLogger("deskpilot.test")
    log.info("hola %s", "mundo")
    log.warning("con extra", extra={"ticket_id": "TCK-000001", "path": tmp_path})

    first, second = _lines(log_file)
    assert set(first) == FIELDS
    assert first["message"] == "hola mundo"
    assert first["level"] == "INFO"
    assert first["logger"] == "deskpilot.test"
    assert first["extra"] == {}
    assert re.match(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}\+00:00$", first["timestamp"])
    assert second["extra"] == {"ticket_id": "TCK-000001", "path": str(tmp_path)}


def test_console_output_is_json(capsys: pytest.CaptureFixture[str]) -> None:
    assert configure_logging("INFO", None) is None
    logging.getLogger("deskpilot.console").info("en consola")
    record = json.loads(capsys.readouterr().err.strip())
    assert record["message"] == "en consola"


def test_request_id_is_present_and_scoped(tmp_path: Path) -> None:
    log_file = configure_logging("INFO", tmp_path, console=False)
    log = logging.getLogger("deskpilot.req")
    log.info("fuera")
    with request_context("req-123") as request_id:
        assert request_id == "req-123"
        log.info("dentro")
    log.info("fuera otra vez")
    assert [line["request_id"] for line in _lines(log_file)] == [None, "req-123", None]


def test_set_request_id_generates_hex_and_resets() -> None:
    token = set_request_id()
    generated = get_request_id()
    assert generated is not None and re.fullmatch(r"[0-9a-f]{32}", generated)
    reset_request_id(token)
    assert get_request_id() is None
    with request_context() as request_id:
        assert get_request_id() == request_id


def test_request_id_is_isolated_between_concurrent_tasks() -> None:
    async def handle(request_id: str) -> str | None:
        with request_context(request_id):
            await asyncio.sleep(0.01)
            return get_request_id()

    async def run() -> list[str | None]:
        return list(await asyncio.gather(handle("a"), handle("b")))

    assert asyncio.run(run()) == ["a", "b"]


def test_level_filters_records(tmp_path: Path) -> None:
    log_file = configure_logging("WARNING", tmp_path, console=False)
    log = logging.getLogger("deskpilot.level")
    log.info("no aparece")
    log.error("sí aparece")
    assert [line["message"] for line in _lines(log_file)] == ["sí aparece"]


def test_reconfiguring_does_not_duplicate_handlers(tmp_path: Path) -> None:
    configure_logging("INFO", tmp_path, console=False)
    log_file = configure_logging("INFO", tmp_path, console=False)
    assert log_file is not None
    logging.getLogger("deskpilot.dup").info("una vez")
    assert len(_lines(log_file)) == 1


def test_file_rotates_and_backups_keep_log_extension(tmp_path: Path) -> None:
    log_file = configure_logging("INFO", tmp_path, console=False, max_bytes=500, backup_count=2)
    log = logging.getLogger("deskpilot.rotate")
    for index in range(40):
        log.info("línea %d con algo de texto para llenar el archivo", index)
    shutdown_logging()
    backups = sorted(p.name for p in tmp_path.glob("deskpilot.*.log"))
    assert backups == ["deskpilot.1.log", "deskpilot.2.log"]
    assert log_file is not None
    for path in (log_file, tmp_path / "deskpilot.1.log"):
        assert all(set(line) == FIELDS for line in _lines(path))


def test_api_key_never_appears_in_logs(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    env_file = tmp_path / "test.env"
    env_file.write_text(f"DESKPILOT_API_KEY={API_KEY}\n", encoding="utf-8")
    settings = load_settings(env_file=env_file)
    log_file = configure_logging_from_settings(settings, log_dir=tmp_path)

    log = logging.getLogger("deskpilot.secret")
    log.info("header X-API-Key=%s", API_KEY)
    log.info("settings: %r", settings)
    log.warning("extra", extra={"headers": {"X-API-Key": API_KEY}, "keys": [API_KEY]})
    try:
        raise RuntimeError(f"bad key {API_KEY}")
    except RuntimeError:
        log.exception("fallo")

    file_text = log_file.read_text(encoding="utf-8")
    console_text = capsys.readouterr().err
    assert API_KEY not in file_text
    assert API_KEY not in console_text
    lines = _lines(log_file)
    assert len(lines) == 4
    assert "[REDACTED:secret]" in lines[0]["message"]
    assert "exception" in lines[3] and "RuntimeError" in lines[3]["exception"]


def test_sensitive_data_is_redacted_in_message_and_extra(tmp_path: Path) -> None:
    log_file = configure_logging("INFO", tmp_path, console=False)
    log = logging.getLogger("deskpilot.pii")
    log.info("usuario dice: mi contraseña es Altiplano#2024", extra={"nip": "NIP 1234"})
    log.info("tarjeta %s", "4111 1111 1111 1111")

    first, second = _lines(log_file)
    assert "Altiplano#2024" not in first["message"]
    assert first["extra"]["nip"] == "NIP [REDACTED:pin]"
    assert second["message"] == "tarjeta [REDACTED:card]"


def test_settings_level_and_default_log_dir(tmp_path: Path) -> None:
    settings = load_settings(env_file=tmp_path / "missing.env")
    log_file = configure_logging_from_settings(settings, log_dir=tmp_path, console=False)
    assert log_file == tmp_path / LOG_FILE_NAME
    assert logging.getLogger().level == logging.getLevelName(settings.app.log_level)
