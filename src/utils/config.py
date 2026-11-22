"""Validated configuration: ``config.yaml`` plus environment variables (S17).

``load_settings`` reads the YAML file, applies the environment overrides
(``DESKPILOT_MODE``, ``LLM_PROVIDER``), reads secrets from the environment or ``.env``
and validates everything with Pydantic. Any problem raises ``ConfigError`` with a
message that names the file, the field and the reason, so the app fails fast at
startup. Secrets are ``SecretStr`` and never show up in ``repr`` or dumps.

The API key is only needed by ``serve``; that command calls ``require_api_key``.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Literal

import yaml
from dotenv import dotenv_values
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    SecretStr,
    ValidationError,
    ValidationInfo,
    field_validator,
    model_validator,
)
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG_PATH = PROJECT_ROOT / "config.yaml"
DEFAULT_ENV_FILE = PROJECT_ROOT / ".env"
MIN_API_KEY_LENGTH = 16
MAX_API_KEY_BYTES = 256  # the API only compares up to this many bytes of X-API-Key

Mode = Literal["local", "fabric"]
LLMProvider = Literal["none", "anthropic", "openai", "gemini"]

LLM_KEY_ENV: dict[str, str] = {
    "anthropic": "ANTHROPIC_API_KEY",
    "openai": "OPENAI_API_KEY",
    "gemini": "GEMINI_API_KEY",
}


class ConfigError(Exception):
    """Invalid or incomplete configuration; the message explains how to fix it."""


class _Section(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class AppConfig(_Section):
    name: str = Field(min_length=1)
    mode: Mode
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"]


class PathsConfig(_Section):
    """Paths relative to the project root are resolved to absolute paths."""

    knowledge_base: Path
    sample: Path
    raw: Path
    sqlite_db: Path
    vectordb: Path
    logs: Path

    @field_validator("*", mode="after")
    @classmethod
    def _resolve(cls, value: Path, info: ValidationInfo) -> Path:
        root: Path = (info.context or {}).get("root", PROJECT_ROOT)
        return value if value.is_absolute() else (root / value).resolve()


class DataConfig(_Section):
    seed: int = Field(ge=0)
    n_tickets: int = Field(ge=1, le=1_000_000)


class ChunkingConfig(_Section):
    strategy: Literal["section"]
    chunk_size: int = Field(ge=50, le=10_000)
    chunk_overlap: int = Field(ge=0)

    @model_validator(mode="after")
    def _overlap_smaller_than_size(self) -> ChunkingConfig:
        if self.chunk_overlap >= self.chunk_size:
            raise ValueError("chunk_overlap must be smaller than chunk_size")
        return self


class EmbeddingsConfig(_Section):
    """``cache_dir`` (optional) is where fastembed keeps the downloaded model."""

    provider: Literal["fastembed", "fake"]
    model: str = Field(min_length=1)
    cache_dir: Path | None = None

    @field_validator("cache_dir", mode="after")
    @classmethod
    def _resolve_cache_dir(cls, value: Path | None, info: ValidationInfo) -> Path | None:
        root: Path = (info.context or {}).get("root", PROJECT_ROOT)
        if value is None or value.is_absolute():
            return value
        return (root / value).resolve()


class VectorDBConfig(_Section):
    provider: Literal["chroma"]
    collection: str = Field(min_length=1)


class RerankConfig(_Section):
    """Cross-encoder veto on top of the similarity threshold (off = threshold only)."""

    enabled: bool = False
    model: str = "BAAI/bge-reranker-v2-m3-int8"  # fastembed TextCrossEncoder, ~0.57 GB
    min_score: float = Field(default=0.02, ge=0.0, le=1.0)  # sigmoid score; below => no evidence
    candidates: int = Field(default=3, ge=1, le=10)  # top articles whose best chunk is scored

    @model_validator(mode="after")
    def _model_required(self) -> RerankConfig:
        if self.enabled and not self.model.strip():
            raise ValueError("retrieval.rerank.model must not be empty when enabled")
        return self


class RetrievalConfig(_Section):
    top_k: int = Field(ge=1, le=50)
    similarity_threshold: float = Field(ge=0.0, le=1.0)
    escalation_margin: float = Field(default=0.05, ge=0.0, le=1.0)
    rerank: RerankConfig = Field(default_factory=RerankConfig)


class LLMModels(_Section):
    anthropic: str = ""
    openai: str = ""
    gemini: str = ""


class LLMConfig(_Section):
    provider: LLMProvider
    timeout_s: float = Field(gt=0, le=300)
    models: LLMModels


class APIConfig(_Section):
    host: str = Field(min_length=1)
    port: int = Field(ge=1, le=65535)
    request_timeout_s: float = Field(gt=0, le=300)
    max_query_chars: int = Field(ge=1, le=10_000)
    max_description_chars: int = Field(ge=1, le=50_000)
    max_body_bytes: int = Field(default=16_384, ge=1_024, le=1_048_576)


class McpConfig(_Section):
    """MCP server (T18): stdio by default (no network); HTTP only when asked for."""

    transport: Literal["stdio", "http"] = "stdio"
    host: str = Field(default="127.0.0.1", min_length=1)
    port: int = Field(default=8001, ge=1, le=65535)
    path: str = Field(default="/mcp", pattern=r"^/[A-Za-z0-9._~/-]*$")


class SlaConfig(_Section):
    """SLA in hours per priority (RN-02)."""

    P1: int = Field(gt=0)
    P2: int = Field(gt=0)
    P3: int = Field(gt=0)
    P4: int = Field(gt=0)


class EvalThresholds(_Section):
    """Targets of ``main.py eval`` in percent (requirements section 12).

    ``min_passed`` is the global minimum: share of all cases that must pass.
    """

    retrieval_top3_pct: float = Field(default=90.0, ge=0, le=100)
    rejection_pct: float = Field(default=100.0, ge=0, le=100)
    classification_pct: float = Field(default=85.0, ge=0, le=100)
    security_pct: float = Field(default=100.0, ge=0, le=100)
    min_passed: float = Field(default=90.0, ge=0, le=100)


class KnownFailure(_Section):
    """A documented limitation: a case allowed to fail, with a reason (never a regression)."""

    id: str = Field(pattern=r"^EV-\d{2,}$")
    reason: str = Field(min_length=1)

    @field_validator("reason", mode="after")
    @classmethod
    def _reason_not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("reason must not be blank")
        return value


class EvalConfig(_Section):
    """``eval:`` section: targets and documented known failures (exit-code contract)."""

    thresholds: EvalThresholds = EvalThresholds()
    known_failures: list[KnownFailure] = []

    @model_validator(mode="after")
    def _unique_ids(self) -> EvalConfig:
        ids = [k.id for k in self.known_failures]
        dup = sorted({i for i in ids if ids.count(i) > 1})
        if dup:
            raise ValueError(f"known_failures has duplicate ids: {', '.join(dup)}")
        return self


_ENV_NAME = r"^[A-Z_][A-Z0-9_]*$"


class FabricConfig(_Section):
    """Names (not values) of the environment variables used in fabric mode."""

    sql_endpoint_env: str = Field(pattern=_ENV_NAME)
    lakehouse_database_env: str = Field(pattern=_ENV_NAME)
    warehouse_endpoint_env: str = Field(pattern=_ENV_NAME)
    warehouse_database_env: str = Field(pattern=_ENV_NAME)
    tenant_id_env: str = Field(pattern=_ENV_NAME)
    client_id_env: str = Field(pattern=_ENV_NAME)
    client_secret_env: str = Field(pattern=_ENV_NAME)


class FileConfig(_Section):
    """Every section of ``config.yaml``."""

    app: AppConfig
    paths: PathsConfig
    data: DataConfig
    chunking: ChunkingConfig
    embeddings: EmbeddingsConfig
    vectordb: VectorDBConfig
    retrieval: RetrievalConfig
    llm: LLMConfig
    api: APIConfig
    mcp: McpConfig = McpConfig()
    eval: EvalConfig = EvalConfig()
    sla_horas: SlaConfig
    fabric: FabricConfig


class FabricCredentials(_Section):
    """Fabric endpoints plus an optional service principal (all three values or none).

    Without a service principal, ``src.utils.fabric`` falls back to
    ``DefaultAzureCredential`` (for example, the identity of ``az login``).
    """

    sql_endpoint: str
    lakehouse_database: str
    warehouse_endpoint: str
    warehouse_database: str
    tenant_id: str | None = None
    client_id: str | None = None
    client_secret: SecretStr | None = None

    @property
    def uses_service_principal(self) -> bool:
        return self.client_secret is not None


class Secrets(_Section):
    api_key: SecretStr | None = None
    anthropic_api_key: SecretStr | None = None
    openai_api_key: SecretStr | None = None
    gemini_api_key: SecretStr | None = None
    fabric: FabricCredentials | None = None


class Settings(FileConfig):
    """Effective configuration: ``config.yaml`` + environment overrides + secrets."""

    secrets: Secrets = Secrets()

    def llm_api_key(self) -> SecretStr | None:
        """Key of the active LLM provider (None for provider ``none``)."""
        if self.llm.provider == "none":
            return None
        key: SecretStr | None = getattr(self.secrets, f"{self.llm.provider}_api_key")
        return key

    def secret_values(self) -> list[str]:
        """Plain values of every configured secret, so the logger can redact them."""
        candidates = [
            self.secrets.api_key,
            self.secrets.anthropic_api_key,
            self.secrets.openai_api_key,
            self.secrets.gemini_api_key,
            self.secrets.fabric.client_secret if self.secrets.fabric else None,
        ]
        return [s.get_secret_value() for s in candidates if s and s.get_secret_value()]


class EnvSettings(BaseSettings):
    """Fixed-name variables read from the environment or the ``.env`` file."""

    model_config = SettingsConfigDict(
        env_ignore_empty=True, extra="ignore", case_sensitive=False, frozen=True
    )

    deskpilot_api_key: SecretStr | None = None
    deskpilot_mode: Mode | None = None
    llm_provider: LLMProvider | None = None
    anthropic_api_key: SecretStr | None = None
    openai_api_key: SecretStr | None = None
    gemini_api_key: SecretStr | None = None


def _format_errors(exc: ValidationError, header: str, *, show_input: bool) -> str:
    lines = [header]
    for error in exc.errors():
        location = ".".join(str(part) for part in error["loc"]) or "(root)"
        message = error["msg"]
        if show_input and error["type"] != "missing":
            shown = repr(error["input"])
            message += f" (got {shown[:60] + '...' if len(shown) > 60 else shown})"
        lines.append(f"  - {location}: {message}")
    return "\n".join(lines)


def _resolve(path: Path | str, root: Path) -> Path:
    candidate = Path(path)
    return candidate if candidate.is_absolute() else root / candidate


def _read_yaml(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise ConfigError(f"Configuration file not found: {path}")
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise ConfigError(f"Invalid YAML in {path}: {exc}") from exc
    if data is None:
        raise ConfigError(f"Configuration file {path} is empty")
    if not isinstance(data, dict):
        raise ConfigError(f"Configuration file {path} must be a YAML mapping of sections")
    return data


def _read_env(env_file: Path) -> EnvSettings:
    try:
        return EnvSettings(_env_file=env_file if env_file.is_file() else None)  # type: ignore[call-arg]
    except ValidationError as exc:
        lines = ["Invalid environment variables (environment or .env):"]
        lines += [f"  - {str(e['loc'][0]).upper()}: {e['msg']}" for e in exc.errors()]
        raise ConfigError("\n".join(lines)) from exc


def _override(data: dict[str, Any], section: str, key: str, value: str | None) -> None:
    if value is not None and isinstance(data.get(section), dict):
        data[section][key] = value


_SERVICE_PRINCIPAL_FIELDS = ("tenant_id_env", "client_id_env", "client_secret_env")


def _fabric_credentials(fabric: FabricConfig, env_file: Path) -> FabricCredentials:
    """Read the fabric variables by the names configured in ``config.yaml``.

    The four endpoint variables are required. The service principal variables go
    together: all three set, or all three empty (then ``DefaultAzureCredential`` is used).
    """
    values: dict[str, str | None] = dict(dotenv_values(env_file)) if env_file.is_file() else {}
    values.update(os.environ)
    names = fabric.model_dump()
    missing = [
        name
        for field, name in names.items()
        if field not in _SERVICE_PRINCIPAL_FIELDS and not values.get(name)
    ]
    sp_missing = [names[f] for f in _SERVICE_PRINCIPAL_FIELDS if not values.get(names[f])]
    if 0 < len(sp_missing) < len(_SERVICE_PRINCIPAL_FIELDS):
        missing += sp_missing
    if missing:
        sp_names = ", ".join(names[f] for f in _SERVICE_PRINCIPAL_FIELDS)
        raise ConfigError(
            "Mode 'fabric' requires these environment variables, which are missing or "
            f"empty: {', '.join(missing)}. The service principal variables ({sp_names}) "
            "go together: set all three, or leave all three empty to use "
            "DefaultAzureCredential (az login). Set them in .env (see .env.example) or "
            "use DESKPILOT_MODE=local."
        )
    return FabricCredentials.model_validate(
        {field.removesuffix("_env"): values.get(name) or None for field, name in names.items()}
    )


def load_settings(
    path: Path | str | None = None,
    *,
    env_file: Path | str | None = None,
    root: Path = PROJECT_ROOT,
) -> Settings:
    """Load and validate the configuration; raise ``ConfigError`` on any problem.

    Relative paths (``path``, ``env_file`` and the ``paths`` section) are resolved
    against ``root`` (the project root), never against the current directory.
    Environment variables take priority over the ``.env`` file.
    """
    config_path = _resolve(path or DEFAULT_CONFIG_PATH, root)
    env_path = _resolve(env_file or DEFAULT_ENV_FILE, root)

    data = _read_yaml(config_path)
    env = _read_env(env_path)
    _override(data, "app", "mode", env.deskpilot_mode)
    _override(data, "llm", "provider", env.llm_provider)

    try:
        file_config = FileConfig.model_validate(data, context={"root": root})
    except ValidationError as exc:
        header = f"Invalid configuration in {config_path}:"
        raise ConfigError(_format_errors(exc, header, show_input=True)) from exc

    secrets = Secrets(
        api_key=env.deskpilot_api_key,
        anthropic_api_key=env.anthropic_api_key,
        openai_api_key=env.openai_api_key,
        gemini_api_key=env.gemini_api_key,
        fabric=(
            _fabric_credentials(file_config.fabric, env_path)
            if file_config.app.mode == "fabric"
            else None
        ),
    )
    settings = Settings(**dict(file_config), secrets=secrets)
    _check_llm(settings)
    return settings


def _check_llm(settings: Settings) -> None:
    provider = settings.llm.provider
    if provider == "none":
        return
    if settings.llm_api_key() is None:
        raise ConfigError(
            f"llm.provider is '{provider}' but {LLM_KEY_ENV[provider]} is not set. "
            "Add it to .env or use LLM_PROVIDER=none."
        )
    if not getattr(settings.llm.models, provider):
        raise ConfigError(
            f"llm.provider is '{provider}' but llm.models.{provider} is empty in config.yaml."
        )


def require_api_key(settings: Settings, command: str = "serve") -> SecretStr:
    """Return the API key required by ``command``; raise ``ConfigError`` if unusable.

    The key must have ``MIN_API_KEY_LENGTH`` to ``MAX_API_KEY_BYTES`` (UTF-8) bytes: a
    longer key could never match, because the API rejects longer headers.
    """
    key = settings.secrets.api_key
    hint = 'Generate one with: python -c "import secrets;print(secrets.token_urlsafe(32))"'
    if key is None:
        raise ConfigError(f"DESKPILOT_API_KEY is required to run '{command}'. {hint}")
    if len(key.get_secret_value()) < MIN_API_KEY_LENGTH:
        raise ConfigError(
            f"DESKPILOT_API_KEY must have at least {MIN_API_KEY_LENGTH} characters. {hint}"
        )
    if len(key.get_secret_value().encode("utf-8")) > MAX_API_KEY_BYTES:
        raise ConfigError(
            f"DESKPILOT_API_KEY must not exceed {MAX_API_KEY_BYTES} bytes (UTF-8). {hint}"
        )
    return key
