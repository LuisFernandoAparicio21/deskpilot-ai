"""Provider ``none``: no LLM at all; the answer service uses its extractive mode (RF-14)."""

from __future__ import annotations

from src.llm.base import LLMError


class NoLLM:
    """Default client. Needs no key and never calls the network."""

    provider = "none"
    model = ""

    def generate(self, system: str, user: str, timeout_s: float) -> str:
        raise LLMError("llm.provider is 'none': use the extractive answer")
