"""Unit tests for the LLM clients with mocked SDKs: arguments, timeout, errors, no key leaks."""

from __future__ import annotations

import logging
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import anthropic
import httpx
import httpx2
import openai
import pytest
from google.genai import errors as genai_errors
from google.genai import types as genai_types
from pydantic import SecretStr

from src.llm import (
    AnthropicClient,
    GeminiClient,
    LLMClient,
    LLMError,
    LLMTimeoutError,
    NoLLM,
    OpenAIClient,
    build_llm,
)
from src.utils.config import Settings, load_settings
from src.utils.logging import configure_logging, shutdown_logging

KEY = "sk-synthetic-test-key-0123456789abcdef"
SYSTEM = "system rules"
USER = "<user_question>hola</user_question>"


class Recorder:
    """Stands in for an SDK method: records kwargs and returns or raises a scripted value."""

    def __init__(self, result: Any = None, error: BaseException | None = None) -> None:
        self.result = result
        self.error = error
        self.calls: list[dict[str, Any]] = []

    def __call__(self, **kwargs: Any) -> Any:
        self.calls.append(kwargs)
        if self.error is not None:
            raise self.error
        return self.result


def _request() -> httpx2.Request:
    return httpx2.Request("POST", "https://example.invalid/v1")


# --- NoLLM and the protocol ----------------------------------------------------------


def test_no_llm_is_an_llm_client_that_refuses_to_generate() -> None:
    client = NoLLM()
    assert isinstance(client, LLMClient)
    assert client.provider == "none"
    with pytest.raises(LLMError, match="extractive"):
        client.generate(SYSTEM, USER, 5)


# --- Anthropic -----------------------------------------------------------------------


def _anthropic_message(*blocks: Any) -> Any:
    return SimpleNamespace(content=list(blocks))


def _anthropic(recorder: Recorder) -> AnthropicClient:
    fake = SimpleNamespace(messages=SimpleNamespace(create=recorder))
    return AnthropicClient(SecretStr(KEY), "claude-sonnet-5-5", client=fake)


def test_anthropic_sends_system_messages_model_and_timeout() -> None:
    text = anthropic.types.TextBlock(type="text", text="1. Espera.", citations=None)
    thinking = SimpleNamespace(type="thinking", thinking="...")
    recorder = Recorder(_anthropic_message(thinking, text))

    assert _anthropic(recorder).generate(SYSTEM, USER, 7.5) == "1. Espera."
    (call,) = recorder.calls
    assert call == {
        "model": "claude-sonnet-5-5",
        "max_tokens": 2048,
        "system": SYSTEM,
        "messages": [{"role": "user", "content": USER}],
        "timeout": 7.5,
    }


def test_anthropic_timeout_and_api_errors_are_mapped() -> None:
    timeout = Recorder(error=anthropic.APITimeoutError(request=_request()))
    with pytest.raises(LLMTimeoutError, match="anthropic"):
        _anthropic(timeout).generate(SYSTEM, USER, 1)

    response = httpx2.Response(401, request=_request())
    denied = Recorder(
        error=anthropic.AuthenticationError(f"bad key {KEY}", response=response, body=None)
    )
    with pytest.raises(LLMError) as excinfo:
        _anthropic(denied).generate(SYSTEM, USER, 1)
    assert KEY not in str(excinfo.value)
    assert excinfo.value.__cause__ is None and excinfo.value.__suppress_context__


def test_anthropic_empty_answer_is_an_error() -> None:
    with pytest.raises(LLMError, match="empty"):
        _anthropic(Recorder(_anthropic_message())).generate(SYSTEM, USER, 1)


def test_anthropic_builds_the_real_sdk_client_lazily_without_retries() -> None:
    client = AnthropicClient(SecretStr(KEY), "claude-sonnet-5-5")
    assert client._client is None  # nothing built until the first call
    sdk = client._get_client()
    assert isinstance(sdk, anthropic.Anthropic)
    assert sdk.max_retries == 0
    assert KEY not in repr(client)


# --- OpenAI --------------------------------------------------------------------------


def _openai(recorder: Recorder) -> OpenAIClient:
    fake = SimpleNamespace(responses=SimpleNamespace(create=recorder))
    return OpenAIClient(SecretStr(KEY), "some-openai-model", client=fake)


def test_openai_sends_instructions_input_model_and_timeout() -> None:
    recorder = Recorder(SimpleNamespace(output_text="1. Reinicia."))
    assert _openai(recorder).generate(SYSTEM, USER, 3) == "1. Reinicia."
    (call,) = recorder.calls
    assert call == {
        "model": "some-openai-model",
        "instructions": SYSTEM,
        "input": USER,
        "max_output_tokens": 2048,
        "timeout": 3,
    }


def test_openai_errors_are_mapped() -> None:
    with pytest.raises(LLMTimeoutError, match="openai"):
        _openai(Recorder(error=openai.APITimeoutError(request=_request()))).generate(
            SYSTEM, USER, 1
        )
    with pytest.raises(LLMError, match="openai"):
        _openai(Recorder(error=openai.APIConnectionError(request=_request()))).generate(
            SYSTEM, USER, 1
        )
    with pytest.raises(LLMError, match="empty"):
        _openai(Recorder(SimpleNamespace(output_text="  "))).generate(SYSTEM, USER, 1)


def test_openai_builds_the_real_sdk_client_without_retries() -> None:
    sdk = OpenAIClient(SecretStr(KEY), "m")._get_client()
    assert isinstance(sdk, openai.OpenAI)
    assert sdk.max_retries == 0


# --- Gemini --------------------------------------------------------------------------


def _gemini(recorder: Recorder) -> GeminiClient:
    fake = SimpleNamespace(models=SimpleNamespace(generate_content=recorder))
    return GeminiClient(SecretStr(KEY), "some-gemini-model", client=fake)


def test_gemini_sends_system_instruction_and_timeout_in_milliseconds() -> None:
    recorder = Recorder(SimpleNamespace(text="1. Revisa el cable."))
    assert _gemini(recorder).generate(SYSTEM, USER, 2.5) == "1. Revisa el cable."
    (call,) = recorder.calls
    assert call["model"] == "some-gemini-model"
    assert call["contents"] == USER
    config = call["config"]
    assert isinstance(config, genai_types.GenerateContentConfig)
    assert config.system_instruction == SYSTEM
    assert config.max_output_tokens == 2048
    assert config.http_options is not None and config.http_options.timeout == 2500


def test_gemini_errors_are_mapped() -> None:
    with pytest.raises(LLMTimeoutError, match="gemini"):
        _gemini(Recorder(error=httpx.ReadTimeout("timed out"))).generate(SYSTEM, USER, 1)
    api_error = genai_errors.ClientError(400, {"error": {"message": "bad", "status": "INVALID"}})
    with pytest.raises(LLMError, match="gemini"):
        _gemini(Recorder(error=api_error)).generate(SYSTEM, USER, 1)
    with pytest.raises(LLMError, match="empty"):
        _gemini(Recorder(SimpleNamespace(text=None))).generate(SYSTEM, USER, 1)


def test_gemini_builds_the_real_sdk_client() -> None:
    from google import genai

    assert isinstance(GeminiClient(SecretStr(KEY), "m")._get_client(), genai.Client)


# --- logs never contain the key or the prompt ----------------------------------------


def test_logs_have_no_key_and_no_prompt(tmp_path: Path) -> None:
    log_file = configure_logging("DEBUG", tmp_path, secrets=[KEY], console=False)
    try:
        response = httpx2.Response(401, request=_request())
        failing = Recorder(
            error=anthropic.AuthenticationError(f"key {KEY}", response=response, body=None)
        )
        with pytest.raises(LLMError):
            _anthropic(failing).generate(SYSTEM, USER, 1)
        _openai(Recorder(SimpleNamespace(output_text="ok"))).generate(SYSTEM, USER, 1)
        logging.getLogger("src.llm").warning("probe %s", "done")
    finally:
        shutdown_logging()
    assert log_file is not None
    content = log_file.read_text(encoding="utf-8")
    assert "probe done" in content
    assert "anthropic" in content and "openai" in content
    assert KEY not in content
    assert SYSTEM not in content and "hola" not in content


# --- factory -------------------------------------------------------------------------


def _settings(tmp_path: Path, provider: str, model: str = "a-model") -> Settings:
    base = load_settings(env_file=tmp_path / "missing.env")
    models = base.llm.models.model_copy(update={provider: model} if provider != "none" else {})
    llm = base.llm.model_copy(update={"provider": provider, "models": models})
    secrets = base.secrets.model_copy(update={f"{provider}_api_key": SecretStr(KEY)})
    return base.model_copy(update={"llm": llm, "secrets": secrets})


@pytest.mark.parametrize(
    ("provider", "expected"),
    [("anthropic", AnthropicClient), ("openai", OpenAIClient), ("gemini", GeminiClient)],
)
def test_build_llm_picks_the_configured_provider(
    tmp_path: Path, provider: str, expected: type
) -> None:
    client = build_llm(_settings(tmp_path, provider))
    assert isinstance(client, expected)
    assert client.provider == provider
    assert getattr(client, "model", None) == "a-model"


def test_build_llm_defaults_to_no_llm(tmp_path: Path) -> None:
    assert isinstance(build_llm(load_settings(env_file=tmp_path / "missing.env")), NoLLM)


def test_build_llm_fails_without_key_or_model(tmp_path: Path) -> None:
    settings = _settings(tmp_path, "openai", model="")
    with pytest.raises(LLMError, match="llm.models.openai"):
        build_llm(settings)
    no_key = _settings(tmp_path, "gemini")
    no_key = no_key.model_copy(
        update={"secrets": no_key.secrets.model_copy(update={"gemini_api_key": None})}
    )
    with pytest.raises(LLMError, match="GEMINI_API_KEY"):
        build_llm(no_key)
