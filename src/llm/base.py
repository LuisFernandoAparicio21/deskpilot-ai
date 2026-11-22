"""The ``LLMClient`` interface, its errors and the shared call wrapper (S17, RNF-06).

Every provider client turns SDK failures into ``LLMError`` (``LLMTimeoutError`` for
timeouts) raised ``from None``: SDK exceptions can carry request details, so they are
never chained or logged. Logs only record provider, model, latency and the error type;
never the API key, the system prompt or the user prompt.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from typing import Protocol, runtime_checkable

logger = logging.getLogger("src.llm")

# Short numbered steps need far less; the margin covers models that think before answering.
DEFAULT_MAX_OUTPUT_TOKENS = 2048


class LLMError(RuntimeError):
    """The LLM call failed; the caller falls back to the extractive answer."""


class LLMTimeoutError(LLMError):
    """The LLM did not answer within the timeout."""


@runtime_checkable
class LLMClient(Protocol):
    """Generates text from a system prompt and a user prompt."""

    @property
    def provider(self) -> str:
        """``none``, ``anthropic``, ``openai`` or ``gemini``."""
        ...

    def generate(self, system: str, user: str, timeout_s: float) -> str:
        """Model answer; raises ``LLMError`` (or ``LLMTimeoutError``) on any failure."""
        ...


def _is_timeout(exc: BaseException) -> bool:
    """SDK timeouts (``APITimeoutError``, ``httpx.ReadTimeout``...) or ``TimeoutError``."""
    return isinstance(exc, TimeoutError) or any(
        "Timeout" in cls.__name__ for cls in type(exc).__mro__
    )


def call_sdk(provider: str, model: str, call: Callable[[], str | None]) -> str:
    """Run one SDK call, map its errors and log only metadata."""
    started = time.perf_counter()
    try:
        text = call()
    except Exception as exc:
        error = type(exc).__name__
        logger.warning(
            "LLM call failed", extra={"provider": provider, "model": model, "error": error}
        )
        if _is_timeout(exc):
            raise LLMTimeoutError(f"{provider} request timed out ({error})") from None
        raise LLMError(f"{provider} request failed ({error})") from None
    elapsed_ms = round((time.perf_counter() - started) * 1000)
    if not text or not text.strip():
        logger.warning(
            "LLM returned an empty answer",
            extra={"provider": provider, "model": model, "elapsed_ms": elapsed_ms},
        )
        raise LLMError(f"{provider} returned an empty answer")
    logger.info(
        "LLM call finished",
        extra={"provider": provider, "model": model, "elapsed_ms": elapsed_ms},
    )
    return text.strip()
