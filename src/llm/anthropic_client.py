"""Claude through the official ``anthropic`` SDK (verified with anthropic 2.12.0).

``Anthropic(api_key=..., max_retries=...)`` and ``client.messages.create(model=...,
max_tokens=..., system=..., messages=[{"role": "user", "content": ...}], timeout=...)``
come from the installed SDK signature and the Messages API reference. The answer is the
concatenation of the ``text`` content blocks (other blocks, such as thinking, are
skipped). Retries are off so ``llm.timeout_s`` bounds the whole call and the extractive
fallback kicks in on time. The SDK is imported only when the first request is made.
"""

from __future__ import annotations

from typing import Any

from pydantic import SecretStr

from src.llm.base import DEFAULT_MAX_OUTPUT_TOKENS, call_sdk


class AnthropicClient:
    provider = "anthropic"

    def __init__(
        self,
        api_key: SecretStr,
        model: str,
        *,
        max_output_tokens: int = DEFAULT_MAX_OUTPUT_TOKENS,
        client: Any | None = None,
    ) -> None:
        self._api_key = api_key
        self.model = model
        self.max_output_tokens = max_output_tokens
        self._client = client

    def __repr__(self) -> str:
        return f"AnthropicClient(model={self.model!r})"

    def _get_client(self) -> Any:
        if self._client is None:
            import anthropic

            self._client = anthropic.Anthropic(
                api_key=self._api_key.get_secret_value(), max_retries=0
            )
        return self._client

    def generate(self, system: str, user: str, timeout_s: float) -> str:
        def _call() -> str:
            message = self._get_client().messages.create(
                model=self.model,
                max_tokens=self.max_output_tokens,
                system=system,
                messages=[{"role": "user", "content": user}],
                timeout=timeout_s,
            )
            return "".join(
                block.text for block in message.content if getattr(block, "type", "") == "text"
            )

        return call_sdk(self.provider, self.model, _call)
