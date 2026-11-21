"""Structured JSON logging with request_id and redaction (RNF-05, RNF-07, S17).

Each record is one JSON line with ``timestamp``, ``level``, ``logger``, ``message``,
``request_id`` and ``extra`` (plus ``exception`` when there is a traceback), written to
the console (stderr) and to ``logs/deskpilot.log`` with size-based rotation.

The current request_id lives in a ``ContextVar`` so it is isolated per request, also
across asyncio tasks. ``RedactionFilter`` removes configured secret values (such as the
API key) and sensitive data detected by ``src.utils.redaction`` before anything is
written.
"""

from __future__ import annotations

import json
import logging
import logging.handlers
import sys
import uuid
from collections.abc import Iterable, Iterator
from contextlib import contextmanager
from contextvars import ContextVar, Token
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

from src.utils.redaction import redact

if TYPE_CHECKING:
    from src.utils.config import Settings

LOG_FILE_NAME = "deskpilot.log"
DEFAULT_MAX_BYTES = 5 * 1024 * 1024
DEFAULT_BACKUP_COUNT = 5
SECRET_PLACEHOLDER = "[REDACTED:secret]"
_MIN_SECRET_LENGTH = 4
_HANDLER_MARK = "_deskpilot_handler"

_request_id: ContextVar[str | None] = ContextVar("request_id", default=None)

# Attributes every LogRecord has; anything else was passed through ``extra``.
_STANDARD_ATTRS = frozenset(logging.LogRecord("", logging.INFO, "", 0, "", None, None).__dict__) | {
    "message",
    "asctime",
    "taskName",
}


# --- request_id ----------------------------------------------------------------------


def new_request_id() -> str:
    """Return a new random request id (32 hex characters)."""
    return uuid.uuid4().hex


def set_request_id(request_id: str | None = None) -> Token[str | None]:
    """Set the request id for the current context (generated if None)."""
    return _request_id.set(request_id or new_request_id())


def get_request_id() -> str | None:
    """Return the request id of the current context, or None outside a request."""
    return _request_id.get()


def reset_request_id(token: Token[str | None]) -> None:
    """Restore the request id that was active before ``set_request_id``."""
    _request_id.reset(token)


@contextmanager
def request_context(request_id: str | None = None) -> Iterator[str]:
    """Run a block with a request id set; yield the id in use."""
    token = set_request_id(request_id)
    try:
        yield _request_id.get() or ""
    finally:
        reset_request_id(token)


# --- formatting and redaction --------------------------------------------------------


def _extra(record: logging.LogRecord) -> dict[str, Any]:
    return {k: v for k, v in record.__dict__.items() if k not in _STANDARD_ATTRS}


class JsonFormatter(logging.Formatter):
    """Format each record as a single JSON line."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(record.created, tz=UTC).isoformat(
                timespec="milliseconds"
            ),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "request_id": get_request_id(),
            "extra": _extra(record),
        }
        if record.exc_info and not record.exc_text:
            record.exc_text = self.formatException(record.exc_info)
        if record.exc_text:
            payload["exception"] = record.exc_text
        return json.dumps(payload, ensure_ascii=False, default=str)


class RedactionFilter(logging.Filter):
    """Redact secret values and sensitive data from message, extra and traceback."""

    def __init__(self, secrets: Iterable[str] = ()) -> None:
        super().__init__()
        # Longest first, so a secret that contains another one is fully replaced.
        self._secrets = sorted(
            {s for s in secrets if len(s) >= _MIN_SECRET_LENGTH}, key=len, reverse=True
        )

    def redact_text(self, text: str) -> str:
        for secret in self._secrets:
            text = text.replace(secret, SECRET_PLACEHOLDER)
        return redact(text)

    def _redact_value(self, value: Any) -> Any:
        if isinstance(value, str):
            return self.redact_text(value)
        if isinstance(value, dict):
            return {k: self._redact_value(v) for k, v in value.items()}
        if isinstance(value, list | tuple | set):
            return [self._redact_value(v) for v in value]
        return value

    def filter(self, record: logging.LogRecord) -> bool:
        record.msg = self.redact_text(record.getMessage())
        record.args = None
        for key, value in _extra(record).items():
            setattr(record, key, self._redact_value(value))
        if record.exc_info and not record.exc_text:
            record.exc_text = logging.Formatter().formatException(record.exc_info)
        if record.exc_text:
            record.exc_text = self.redact_text(record.exc_text)
        if record.stack_info:
            record.stack_info = self.redact_text(record.stack_info)
        return True


# --- setup ---------------------------------------------------------------------------


def _backup_name(default_name: str) -> str:
    """``deskpilot.log.1`` -> ``deskpilot.1.log``, so backups match ``logs/*.log``."""
    base, _, index = default_name.rpartition(".")
    stem = Path(base)
    return str(stem.with_name(f"{stem.stem}.{index}{stem.suffix}"))


def shutdown_logging() -> None:
    """Remove and close the handlers installed by ``configure_logging``."""
    root = logging.getLogger()
    for handler in list(root.handlers):
        if getattr(handler, _HANDLER_MARK, False):
            root.removeHandler(handler)
            handler.close()


def configure_logging(
    level: str = "INFO",
    log_dir: Path | None = None,
    *,
    secrets: Iterable[str] = (),
    console: bool = True,
    max_bytes: int = DEFAULT_MAX_BYTES,
    backup_count: int = DEFAULT_BACKUP_COUNT,
) -> Path | None:
    """Configure the root logger with JSON handlers; return the log file path, if any.

    Calling it again replaces the previous DeskPilot handlers (no duplicates).
    """
    shutdown_logging()
    redaction = RedactionFilter(secrets)
    formatter = JsonFormatter()
    handlers: list[logging.Handler] = []
    if console:
        handlers.append(logging.StreamHandler(sys.stderr))
    log_file: Path | None = None
    if log_dir is not None:
        log_dir.mkdir(parents=True, exist_ok=True)
        log_file = log_dir / LOG_FILE_NAME
        file_handler = logging.handlers.RotatingFileHandler(
            log_file, maxBytes=max_bytes, backupCount=backup_count, encoding="utf-8"
        )
        file_handler.namer = _backup_name
        handlers.append(file_handler)

    root = logging.getLogger()
    root.setLevel(level)
    for handler in handlers:
        handler.addFilter(redaction)
        handler.setFormatter(formatter)
        setattr(handler, _HANDLER_MARK, True)
        root.addHandler(handler)
    return log_file


def configure_logging_from_settings(
    settings: Settings, *, log_dir: Path | None = None, console: bool = True
) -> Path:
    """Configure logging from ``settings``: level, ``paths.logs`` and secrets to redact."""
    directory = log_dir or settings.paths.logs
    configure_logging(
        settings.app.log_level,
        directory,
        secrets=settings.secret_values(),
        console=console,
    )
    return directory / LOG_FILE_NAME
