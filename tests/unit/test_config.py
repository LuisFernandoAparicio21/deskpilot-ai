"""Unit tests for the validated configuration (S17: fail fast with a clear message)."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
import yaml
from pydantic import SecretStr, ValidationError

from src.utils.config import (
    PROJECT_ROOT,
    ConfigError,
    load_settings,
    require_api_key,
)

API_KEY = "synthetic-api-key-0123456789-abcdef"
FABRIC_VARS = {
    "FABRIC_SQL_ENDPOINT": "example-sql.datawarehouse.fabric.microsoft.com",
    "FABRIC_LAKEHOUSE_DATABASE": "lh_deskpilot",
    "FABRIC_WAREHOUSE_ENDPOINT": "example-wh.datawarehouse.fabric.microsoft.com",
    "FABRIC_WAREHOUSE_DATABASE": "wh_deskpilot",
    "AZURE_TENANT_ID": "00000000-0000-0000-0000-000000000000",
    "AZURE_CLIENT_ID": "11111111-1111-1111-1111-111111111111",
    "AZURE_CLIENT_SECRET": "synthetic-client-secret-value",
}
ENV_VARS = [
    "DESKPILOT_API_KEY",
    "DESKPILOT_MODE",
    "LLM_PROVIDER",
    "ANTHROPIC_API_KEY",
    "OPENAI_API_KEY",
    "GEMINI_API_KEY",
    *FABRIC_VARS,
]

ConfigWriter = Callable[[Callable[[dict[str, Any]], None]], Path]


@pytest.fixture(autouse=True)
def clean_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Isolate every test from the developer's real environment variables."""
    for name in ENV_VARS:
        monkeypatch.delenv(name, raising=False)


@pytest.fixture
def no_env_file(tmp_path: Path) -> Path:
    return tmp_path / "missing.env"


@pytest.fixture
def write_config(tmp_path: Path) -> ConfigWriter:
    """Copy the repo config.yaml to tmp_path, apply a mutation and return the new path."""

    def _write(mutate: Callable[[dict[str, Any]], None]) -> Path:
        data = yaml.safe_load((PROJECT_ROOT / "config.yaml").read_text(encoding="utf-8"))
        mutate(data)
        path = tmp_path / "config.yaml"
        path.write_text(yaml.safe_dump(data), encoding="utf-8")
        return path

    return _write


def _env_file(tmp_path: Path, values: dict[str, str]) -> Path:
    path = tmp_path / "test.env"
    path.write_text("".join(f"{k}={v}\n" for k, v in values.items()), encoding="utf-8")
    return path


# --- Valid configuration -------------------------------------------------------------


def test_repo_config_is_valid(no_env_file: Path) -> None:
    settings = load_settings(PROJECT_ROOT / "config.yaml", env_file=no_env_file)
    assert settings.app.name == "deskpilot-ai"
    assert settings.app.mode == "local"
    assert settings.retrieval.top_k == 3
    assert settings.llm.provider == "none"
    assert settings.sla_horas.P1 == 4
    assert settings.secrets.api_key is None
    assert settings.secrets.fabric is None
    assert settings.llm_api_key() is None


def test_default_path_and_paths_resolved_against_project_root(
    no_env_file: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)  # the current directory must not matter
    for settings in (
        load_settings(env_file=no_env_file),
        load_settings("config.yaml", env_file=no_env_file),
    ):
        assert settings.paths.logs == PROJECT_ROOT / "logs"
        assert settings.paths.knowledge_base == PROJECT_ROOT / "data" / "knowledge_base"
        assert all(p.is_absolute() for p in settings.paths.model_dump().values())


def test_absolute_paths_are_kept(write_config: ConfigWriter, no_env_file: Path) -> None:
    absolute = (PROJECT_ROOT / "elsewhere").resolve()
    path = write_config(lambda d: d["paths"].update(logs=str(absolute)))
    assert load_settings(path, env_file=no_env_file).paths.logs == absolute


def test_embeddings_cache_dir_is_resolved_against_project_root(no_env_file: Path) -> None:
    settings = load_settings(env_file=no_env_file)
    assert settings.embeddings.cache_dir == PROJECT_ROOT / "data" / "vectordb" / "models"


def test_embeddings_cache_dir_is_optional(write_config: ConfigWriter, no_env_file: Path) -> None:
    path = write_config(lambda d: d["embeddings"].pop("cache_dir"))
    assert load_settings(path, env_file=no_env_file).embeddings.cache_dir is None


def test_settings_are_immutable(no_env_file: Path) -> None:
    settings = load_settings(env_file=no_env_file)
    with pytest.raises(ValidationError):
        settings.app.name = "other"


# --- Clear errors --------------------------------------------------------------------


def test_missing_file_fails_with_clear_message(tmp_path: Path) -> None:
    with pytest.raises(ConfigError, match="Configuration file not found"):
        load_settings(tmp_path / "nope.yaml")


@pytest.mark.parametrize(
    ("content", "message"),
    [
        ("app: [unclosed", "Invalid YAML"),
        ("", "is empty"),
        ("- just\n- a list\n", "must be a YAML mapping"),
    ],
)
def test_malformed_yaml_fails(tmp_path: Path, content: str, message: str) -> None:
    path = tmp_path / "config.yaml"
    path.write_text(content, encoding="utf-8")
    with pytest.raises(ConfigError, match=message):
        load_settings(path, env_file=tmp_path / "missing.env")


@pytest.mark.parametrize(
    ("section", "field", "value"),
    [
        ("retrieval", "top_k", 0),
        ("retrieval", "similarity_threshold", 1.5),
        ("api", "port", 70000),
        ("llm", "timeout_s", -1),
        ("data", "n_tickets", 0),
        ("app", "mode", "cloud"),
        ("app", "log_level", "VERBOSE"),
        ("embeddings", "provider", "magic"),
        ("fabric", "client_secret_env", "not a var name"),
    ],
)
def test_out_of_range_values_fail_with_field_location(
    write_config: ConfigWriter, no_env_file: Path, section: str, field: str, value: object
) -> None:
    path = write_config(lambda d: d[section].update({field: value}))
    with pytest.raises(ConfigError) as excinfo:
        load_settings(path, env_file=no_env_file)
    message = str(excinfo.value)
    assert f"Invalid configuration in {path}" in message
    assert f"{section}.{field}" in message


def test_missing_section_and_unknown_key_are_reported(
    write_config: ConfigWriter, no_env_file: Path
) -> None:
    def mutate(data: dict[str, Any]) -> None:
        del data["api"]
        data["retrieval"]["topk"] = 5

    with pytest.raises(ConfigError) as excinfo:
        load_settings(write_config(mutate), env_file=no_env_file)
    message = str(excinfo.value)
    assert "api: Field required" in message
    assert "retrieval.topk: Extra inputs are not permitted" in message


def test_chunk_overlap_must_be_smaller_than_chunk_size(
    write_config: ConfigWriter, no_env_file: Path
) -> None:
    path = write_config(lambda d: d["chunking"].update(chunk_size=100, chunk_overlap=100))
    with pytest.raises(ConfigError, match="chunk_overlap must be smaller than chunk_size"):
        load_settings(path, env_file=no_env_file)


# --- Environment: secrets and mode ---------------------------------------------------


def test_secrets_are_read_from_env_file(tmp_path: Path) -> None:
    env_file = _env_file(tmp_path, {"DESKPILOT_API_KEY": API_KEY, "OPENAI_API_KEY": ""})
    settings = load_settings(env_file=env_file)
    assert isinstance(settings.secrets.api_key, SecretStr)
    assert settings.secrets.api_key.get_secret_value() == API_KEY
    assert settings.secrets.openai_api_key is None  # empty values count as unset


def test_environment_variable_overrides_env_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    env_file = _env_file(tmp_path, {"DESKPILOT_API_KEY": "from-file-0123456789"})
    monkeypatch.setenv("DESKPILOT_API_KEY", API_KEY)
    settings = load_settings(env_file=env_file)
    assert settings.secrets.api_key is not None
    assert settings.secrets.api_key.get_secret_value() == API_KEY


def test_invalid_mode_in_environment_fails(
    no_env_file: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("DESKPILOT_MODE", "prod")
    with pytest.raises(ConfigError, match="DESKPILOT_MODE"):
        load_settings(env_file=no_env_file)


def test_fabric_mode_without_variables_lists_every_missing_name(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("DESKPILOT_MODE", "fabric")
    env_file = _env_file(tmp_path, {"DESKPILOT_API_KEY": API_KEY, "AZURE_TENANT_ID": "x"})
    with pytest.raises(ConfigError) as excinfo:
        load_settings(env_file=env_file)
    message = str(excinfo.value)
    assert "fabric" in message
    missing = message.split("empty:")[1].split(".")[0]
    for name in FABRIC_VARS:
        assert (name in missing) is (name != "AZURE_TENANT_ID")
    assert API_KEY not in message


def test_fabric_mode_with_variables_builds_credentials(tmp_path: Path) -> None:
    env_file = _env_file(tmp_path, {"DESKPILOT_MODE": "fabric", **FABRIC_VARS})
    settings = load_settings(env_file=env_file)
    assert settings.app.mode == "fabric"
    fabric = settings.secrets.fabric
    assert fabric is not None
    assert fabric.sql_endpoint == FABRIC_VARS["FABRIC_SQL_ENDPOINT"]
    assert fabric.client_secret.get_secret_value() == FABRIC_VARS["AZURE_CLIENT_SECRET"]
    assert FABRIC_VARS["AZURE_CLIENT_SECRET"] not in repr(settings)
    assert fabric.uses_service_principal


SERVICE_PRINCIPAL_VARS = ("AZURE_TENANT_ID", "AZURE_CLIENT_ID", "AZURE_CLIENT_SECRET")
ENDPOINT_VARS = {k: v for k, v in FABRIC_VARS.items() if k not in SERVICE_PRINCIPAL_VARS}


def test_fabric_mode_without_service_principal_uses_default_credential(
    tmp_path: Path,
) -> None:
    env_file = _env_file(tmp_path, {"DESKPILOT_MODE": "fabric", **ENDPOINT_VARS})
    fabric = load_settings(env_file=env_file).secrets.fabric
    assert fabric is not None
    assert fabric.warehouse_database == ENDPOINT_VARS["FABRIC_WAREHOUSE_DATABASE"]
    assert (fabric.tenant_id, fabric.client_id, fabric.client_secret) == (None, None, None)
    assert not fabric.uses_service_principal


@pytest.mark.parametrize("present", SERVICE_PRINCIPAL_VARS)
def test_fabric_mode_with_partial_service_principal_fails(tmp_path: Path, present: str) -> None:
    values = {"DESKPILOT_MODE": "fabric", **ENDPOINT_VARS, present: FABRIC_VARS[present]}
    with pytest.raises(ConfigError) as excinfo:
        load_settings(env_file=_env_file(tmp_path, values))
    message = str(excinfo.value)
    for name in SERVICE_PRINCIPAL_VARS:
        assert (name in message.split("empty:")[1].split(".")[0]) is (name != present)
    assert "DefaultAzureCredential" in message
    assert FABRIC_VARS["AZURE_CLIENT_SECRET"] not in message


def test_llm_provider_requires_its_key_and_model(
    tmp_path: Path, write_config: ConfigWriter, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("LLM_PROVIDER", "anthropic")
    with pytest.raises(ConfigError, match="ANTHROPIC_API_KEY"):
        load_settings(env_file=tmp_path / "missing.env")

    env_file = _env_file(tmp_path, {"ANTHROPIC_API_KEY": "synthetic-anthropic-key"})
    no_model = write_config(lambda d: d["llm"]["models"].update(anthropic=""))
    with pytest.raises(ConfigError, match=r"llm\.models\.anthropic"):
        load_settings(no_model, env_file=env_file)

    path = write_config(lambda d: d["llm"]["models"].update(anthropic="some-model"))
    settings = load_settings(path, env_file=env_file)
    assert settings.llm.provider == "anthropic"
    assert settings.llm_api_key() is not None


# --- API key: required only for serve, never exposed ---------------------------------


def test_require_api_key_fails_when_missing(no_env_file: Path) -> None:
    settings = load_settings(env_file=no_env_file)  # other commands work without it
    with pytest.raises(ConfigError, match=r"DESKPILOT_API_KEY is required .*serve"):
        require_api_key(settings)


def test_require_api_key_rejects_short_keys(tmp_path: Path) -> None:
    settings = load_settings(env_file=_env_file(tmp_path, {"DESKPILOT_API_KEY": "short"}))
    with pytest.raises(ConfigError, match="at least 16 characters") as excinfo:
        require_api_key(settings)
    assert "short" not in str(excinfo.value).replace("at least", "")


def test_require_api_key_returns_secret(tmp_path: Path) -> None:
    settings = load_settings(env_file=_env_file(tmp_path, {"DESKPILOT_API_KEY": API_KEY}))
    key = require_api_key(settings)
    assert isinstance(key, SecretStr)
    assert key.get_secret_value() == API_KEY


def test_api_key_never_appears_in_repr_str_or_dump(tmp_path: Path) -> None:
    settings = load_settings(env_file=_env_file(tmp_path, {"DESKPILOT_API_KEY": API_KEY}))
    for rendered in (
        repr(settings),
        str(settings),
        repr(settings.secrets),
        settings.model_dump_json(),
        str(settings.model_dump()),
    ):
        assert API_KEY not in rendered


def test_secret_values_lists_configured_secrets(tmp_path: Path) -> None:
    env_file = _env_file(tmp_path, {"DESKPILOT_API_KEY": API_KEY, "DESKPILOT_MODE": "fabric"})
    env_file.write_text(
        env_file.read_text(encoding="utf-8")
        + "".join(f"{k}={v}\n" for k, v in FABRIC_VARS.items()),
        encoding="utf-8",
    )
    values = load_settings(env_file=env_file).secret_values()
    assert API_KEY in values
    assert FABRIC_VARS["AZURE_CLIENT_SECRET"] in values
