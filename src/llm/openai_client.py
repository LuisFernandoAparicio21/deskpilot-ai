"""OpenAI through the official ``openai`` SDK and the Responses API (verified with 3.57.0).

``OpenAI(api_key=..., max_retries=...)`` and ``client.responses.create(model=...,
instructions=..., input=..., max_output_tokens=..., timeout=...)`` come from the
installed SDK signature and the official text-generation guide; ``response.output_text``
joins the text outputs. Retries are off, so one attempt is made. A float ``timeout`` is applied by the
SDK to each httpx phase (connect, write, read, pool: verified by building a request with
``timeout=7.5``), so it is not a total deadline. The SDK is
imported only when the first request is made.
"""

from __future__ import annotations

from typing import Any

from pydantic import SecretStr

from src.llm.base import DEFAULT_MAX_OUTPUT_TOKENS, call_sdk


class OpenAIClient:
    provider = "openai"

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
        return f"OpenAIClient(model={self.model!r})"

    def _get_client(self) -> Any:
        if self._client is None:
            import openai

            self._client = openai.OpenAI(api_key=self._api_key.get_secret_value(), max_retries=0)
        return self._client

    def generate(self, system: str, user: str, timeout_s: float) -> str:
        def _call() -> str:
            response = self._get_client().responses.create(
                model=self.model,
                instructions=system,
                input=user,
                max_output_tokens=self.max_output_tokens,
                timeout=timeout_s,
            )
            return str(response.output_text)

        return call_sdk(self.provider, self.model, _call)
