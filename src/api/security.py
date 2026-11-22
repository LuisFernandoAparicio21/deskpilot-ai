"""``X-API-Key`` authentication with a constant-time comparison (S8, S16, RNF-02).

Missing and wrong keys get the same 401 body, so nothing tells an attacker which case
it was. The key is compared as bytes with ``hmac.compare_digest`` (the ``str`` form only
accepts ASCII and would raise on other input); it is never logged.

Headers longer than ``MAX_KEY_BYTES`` are rejected. To avoid silently locking out a
configured key that long, ``src.utils.config.require_api_key`` refuses at startup any
key over that limit, with a clear error.
"""

from __future__ import annotations

import hmac
import logging
from collections.abc import Callable, Coroutine
from typing import Annotated, Any

from fastapi import Security
from fastapi.security import APIKeyHeader

from src.api.errors import ApiError
from src.utils.config import MAX_API_KEY_BYTES

logger = logging.getLogger(__name__)

API_KEY_HEADER = "X-API-Key"
MAX_KEY_BYTES = MAX_API_KEY_BYTES
_scheme = APIKeyHeader(name=API_KEY_HEADER, auto_error=False, description="Service API key.")


def keys_match(provided: str | None, expected: str) -> bool:
    """Constant-time equality; a missing key never matches."""
    if provided is None:
        return False
    given = provided.encode("utf-8")[:MAX_KEY_BYTES]
    wanted = expected.encode("utf-8")
    ok = hmac.compare_digest(given, wanted)
    return ok and len(provided.encode("utf-8")) <= MAX_KEY_BYTES


def require_api_key(expected: str) -> Callable[..., Coroutine[Any, Any, None]]:
    """FastAPI dependency that answers 401 unless ``X-API-Key`` equals ``expected``."""

    async def dependency(provided: Annotated[str | None, Security(_scheme)]) -> None:
        if not keys_match(provided, expected):
            logger.warning("Request rejected: missing or invalid API key")
            raise ApiError(401, headers={"WWW-Authenticate": API_KEY_HEADER})

    return dependency
