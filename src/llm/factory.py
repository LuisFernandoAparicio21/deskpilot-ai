"""Pick the LLM client named by ``llm.provider`` (config.yaml or ``LLM_PROVIDER``)."""

from __future__ import annotations

from src.llm.anthropic_client import AnthropicClient
from src.llm.base import LLMClient, LLMError
from src.llm.gemini_client import GeminiClient
from src.llm.none import NoLLM
from src.llm.openai_client import OpenAIClient
from src.utils.config import LLM_KEY_ENV, Settings

_CLIENTS: dict[str, type[AnthropicClient | OpenAIClient | GeminiClient]] = {
    "anthropic": AnthropicClient,
    "openai": OpenAIClient,
    "gemini": GeminiClient,
}


def build_llm(settings: Settings) -> LLMClient:
    """``none`` -> ``NoLLM``; otherwise the provider client with its key and model.

    ``load_settings`` already fails fast on a missing key or model; this check keeps
    hand-built settings honest too.
    """
    provider = settings.llm.provider
    if provider == "none":
        return NoLLM()
    key = settings.llm_api_key()
    if key is None or not key.get_secret_value():
        raise LLMError(f"llm.provider is '{provider}' but {LLM_KEY_ENV[provider]} is not set")
    model: str = getattr(settings.llm.models, provider)
    if not model:
        raise LLMError(f"llm.provider is '{provider}' but llm.models.{provider} is empty")
    return _CLIENTS[provider](key, model)
