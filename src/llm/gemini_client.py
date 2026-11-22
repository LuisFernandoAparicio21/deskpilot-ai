"""Gemini through the official ``google-genai`` SDK (verified with google-genai 3.6.1).

``genai.Client(api_key=...)`` and ``client.models.generate_content(model=..., contents=...,
config=types.GenerateContentConfig(system_instruction=..., max_output_tokens=...,
http_options=types.HttpOptions(timeout=...)))`` come from the installed SDK and the
official generateContent guide. ``HttpOptions.timeout`` is in **milliseconds** (field
description in the installed SDK). The Gemini docs now recommend the Interactions API
for new code and keep ``generateContent`` as supported; it is used here because its
signature is fully typed in the installed SDK. ``response.text`` may be None.
"""

from __future__ import annotations

from typing import Any

from pydantic import SecretStr

from src.llm.base import DEFAULT_MAX_OUTPUT_TOKENS, call_sdk


class GeminiClient:
    provider = "gemini"

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
        return f"GeminiClient(model={self.model!r})"

    def _get_client(self) -> Any:
        if self._client is None:
            from google import genai

            self._client = genai.Client(api_key=self._api_key.get_secret_value())
        return self._client

    def generate(self, system: str, user: str, timeout_s: float) -> str:
        from google.genai import types

        config = types.GenerateContentConfig(
            system_instruction=system,
            max_output_tokens=self.max_output_tokens,
            http_options=types.HttpOptions(timeout=max(1, round(timeout_s * 1000))),
        )

        def _call() -> str | None:
            response = self._get_client().models.generate_content(
                model=self.model, contents=user, config=config
            )
            text: str | None = response.text
            return text

        return call_sdk(self.provider, self.model, _call)
