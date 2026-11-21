"""Unit tests for src/utils/fabric.py with mocks (S6, S16, RF-18).

No test opens a network connection: ``pyodbc`` is replaced by a fake module in
``sys.modules`` and the azure-identity credentials by fakes that record their calls.
"""

from __future__ import annotations

import logging
import struct
import subprocess
import sys
import types
from collections.abc import Iterator
from typing import Any

import azure.identity
import pytest
from azure.core.credentials import AccessToken
from azure.core.exceptions import ClientAuthenticationError
from pydantic import SecretStr

from src.utils import fabric as fabric_module
from src.utils.config import PROJECT_ROOT, ConfigError, FabricCredentials, load_settings
from src.utils.fabric import (
    DEFAULT_ENV_NAMES,
    ODBC_DRIVER,
    SQL_COPT_SS_ACCESS_TOKEN,
    SQL_TOKEN_SCOPE,
    FabricAuthError,
    FabricConnectionError,
    FabricConnectionFactory,
    FabricDriverError,
    build_connection_string,
    encode_access_token,
)

TOKEN = "eyJ0eXAiOiJKV1QiLCJhbGciOiJSUzI1NiJ9.synthetic-token-for-tests"
SECRET = "synthetic-client-secret-value"
SQL_HOST = "abc123.datawarehouse.fabric.microsoft.com"
WH_HOST = "def456.datawarehouse.fabric.microsoft.com"
SP_ENV_NAMES = ("AZURE_TENANT_ID", "AZURE_CLIENT_ID", "AZURE_CLIENT_SECRET")


def _credentials(*, service_principal: bool = True, **overrides: Any) -> FabricCredentials:
    data: dict[str, Any] = {
        "sql_endpoint": SQL_HOST,
        "lakehouse_database": "lh_deskpilot",
        "warehouse_endpoint": WH_HOST,
        "warehouse_database": "wh_deskpilot",
    }
    if service_principal:
        data |= {
            "tenant_id": "00000000-0000-0000-0000-000000000000",
            "client_id": "11111111-1111-1111-1111-111111111111",
            "client_secret": SecretStr(SECRET),
        }
    return FabricCredentials.model_validate(data | overrides)


class FakeCredential:
    """Stands in for ClientSecretCredential / DefaultAzureCredential."""

    instances: list[FakeCredential] = []

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self.args = args
        self.kwargs = kwargs
        self.scopes: list[tuple[str, ...]] = []
        FakeCredential.instances.append(self)

    def get_token(self, *scopes: str, **kwargs: Any) -> AccessToken:
        self.scopes.append(scopes)
        return AccessToken(TOKEN, 4_102_444_800)


class FailingCredential(FakeCredential):
    def get_token(self, *scopes: str, **kwargs: Any) -> AccessToken:
        raise ClientAuthenticationError(message="AADSTS7000215: invalid client secret")


class FakePyodbcError(Exception):
    """Mimics pyodbc.Error: args[0] is the SQLSTATE."""


@pytest.fixture
def fake_pyodbc(monkeypatch: pytest.MonkeyPatch) -> Iterator[types.SimpleNamespace]:
    calls: list[dict[str, Any]] = []

    def connect(connstring: str, **kwargs: Any) -> object:
        calls.append({"connstring": connstring, **kwargs})
        return object()

    module = types.SimpleNamespace(
        Error=FakePyodbcError,
        connect=connect,
        drivers=lambda: ["SQL Server", ODBC_DRIVER],
        calls=calls,
    )
    monkeypatch.setitem(sys.modules, "pyodbc", module)
    yield module


@pytest.fixture(autouse=True)
def fake_identity(monkeypatch: pytest.MonkeyPatch) -> dict[str, type[FakeCredential]]:
    FakeCredential.instances = []
    secret_cls = type("ClientSecretCredential", (FakeCredential,), {})
    default_cls = type("DefaultAzureCredential", (FakeCredential,), {})
    monkeypatch.setattr(azure.identity, "ClientSecretCredential", secret_cls)
    monkeypatch.setattr(azure.identity, "DefaultAzureCredential", default_cls)
    return {"secret": secret_cls, "default": default_cls}


# --- Settings and fail-fast validation -------------------------------------------------


def test_from_settings_in_local_mode_fails_with_clear_message(tmp_path: Any) -> None:
    settings = load_settings(env_file=tmp_path / "missing.env")
    with pytest.raises(ConfigError, match="DESKPILOT_MODE=fabric"):
        FabricConnectionFactory.from_settings(settings)


def test_from_settings_in_fabric_mode(tmp_path: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    env = tmp_path / "test.env"
    env.write_text(
        "DESKPILOT_MODE=fabric\n"
        f"FABRIC_SQL_ENDPOINT={SQL_HOST}\nFABRIC_LAKEHOUSE_DATABASE=lh\n"
        f"FABRIC_WAREHOUSE_ENDPOINT={WH_HOST}\nFABRIC_WAREHOUSE_DATABASE=wh\n",
        encoding="utf-8",
    )
    for name in ("DESKPILOT_MODE", *DEFAULT_ENV_NAMES.values(), *SP_ENV_NAMES):
        monkeypatch.delenv(name, raising=False)
    factory = FabricConnectionFactory.from_settings(load_settings(env_file=env))
    assert factory.auth_mode == "default_credential"


@pytest.mark.parametrize(
    ("field", "value", "env_name"),
    [
        ("sql_endpoint", f"tcp:{SQL_HOST},1433", "FABRIC_SQL_ENDPOINT"),
        ("sql_endpoint", f"{SQL_HOST};UID=x;PWD={SECRET}", "FABRIC_SQL_ENDPOINT"),
        (
            "warehouse_endpoint",
            "https://app.fabric.microsoft.com/groups/1",
            "FABRIC_WAREHOUSE_ENDPOINT",
        ),
        ("warehouse_endpoint", "localhost", "FABRIC_WAREHOUSE_ENDPOINT"),
        ("lakehouse_database", f"lh;PWD={SECRET}", "FABRIC_LAKEHOUSE_DATABASE"),
        ("warehouse_database", "wh{x}", "FABRIC_WAREHOUSE_DATABASE"),
        ("warehouse_database", "   ", "FABRIC_WAREHOUSE_DATABASE"),
    ],
)
def test_invalid_values_fail_fast_without_echoing_them(
    field: str, value: str, env_name: str
) -> None:
    with pytest.raises(ConfigError) as excinfo:
        FabricConnectionFactory(_credentials(**{field: value}))
    message = str(excinfo.value)
    assert env_name in message
    assert SECRET not in message
    assert value.strip() == "" or value not in message


def test_database_names_with_spaces_are_allowed() -> None:
    factory = FabricConnectionFactory(_credentials(warehouse_database="NYC Taxi"))
    assert "Database=NYC Taxi;" in build_connection_string(WH_HOST, "NYC Taxi")
    assert factory.auth_mode == "service_principal"


# --- Connection string and token -------------------------------------------------------


def test_connection_string_uses_driver_18_encryption_and_no_credentials() -> None:
    connstring = build_connection_string(SQL_HOST, "lh_deskpilot")
    assert connstring == (
        "Driver={ODBC Driver 18 for SQL Server};"
        f"Server=tcp:{SQL_HOST},1433;Database=lh_deskpilot;"
        "Encrypt=yes;TrustServerCertificate=no;"
    )
    for forbidden in ("UID=", "PWD=", "Authentication=", "Trusted_Connection", "MultipleActive"):
        assert forbidden.lower() not in connstring.lower()


def test_encode_access_token_is_length_prefixed_utf16le() -> None:
    assert encode_access_token("ab") == b"\x04\x00\x00\x00a\x00b\x00"
    encoded = encode_access_token(TOKEN)
    (size,) = struct.unpack("<I", encoded[:4])
    assert size == 2 * len(TOKEN) == len(encoded) - 4
    assert encoded[4:].decode("utf-16-le") == TOKEN


# --- Connections ---------------------------------------------------------------------


@pytest.mark.parametrize(
    ("method", "host", "database"),
    [
        ("connect_lakehouse", SQL_HOST, "lh_deskpilot"),
        ("connect_warehouse", WH_HOST, "wh_deskpilot"),
    ],
)
def test_connect_requests_token_and_passes_it_in_attrs_before(
    fake_pyodbc: types.SimpleNamespace, method: str, host: str, database: str
) -> None:
    factory = FabricConnectionFactory(_credentials(), timeout_s=12)
    getattr(factory, method)()
    (credential,) = FakeCredential.instances
    assert credential.scopes == [(SQL_TOKEN_SCOPE,)]
    assert SQL_TOKEN_SCOPE == "https://database.windows.net/.default"
    (call,) = fake_pyodbc.calls
    assert call["connstring"] == build_connection_string(host, database)
    assert call["attrs_before"] == {SQL_COPT_SS_ACCESS_TOKEN: encode_access_token(TOKEN)}
    assert SQL_COPT_SS_ACCESS_TOKEN == 1256
    assert call["timeout"] == 12
    assert call["autocommit"] is False


def test_service_principal_uses_client_secret_credential(
    fake_pyodbc: types.SimpleNamespace, fake_identity: dict[str, type[FakeCredential]]
) -> None:
    factory = FabricConnectionFactory(_credentials())
    factory.connect_lakehouse()
    factory.connect_warehouse()
    (credential,) = FakeCredential.instances  # built once and reused
    assert isinstance(credential, fake_identity["secret"])
    assert credential.kwargs == {
        "tenant_id": "00000000-0000-0000-0000-000000000000",
        "client_id": "11111111-1111-1111-1111-111111111111",
        "client_secret": SECRET,
    }
    assert len(credential.scopes) == 2  # a fresh token per connection


def test_without_service_principal_uses_default_credential(
    fake_pyodbc: types.SimpleNamespace, fake_identity: dict[str, type[FakeCredential]]
) -> None:
    factory = FabricConnectionFactory(_credentials(service_principal=False))
    assert factory.auth_mode == "default_credential"
    factory.connect_warehouse()
    (credential,) = FakeCredential.instances
    assert isinstance(credential, fake_identity["default"])
    assert credential.args == () and credential.kwargs == {}


def test_injected_credential_is_used(fake_pyodbc: types.SimpleNamespace) -> None:
    injected = FakeCredential()
    FabricConnectionFactory(_credentials(), credential=injected).connect_lakehouse()
    assert FakeCredential.instances == [injected]
    assert injected.scopes == [(SQL_TOKEN_SCOPE,)]


# --- Errors ----------------------------------------------------------------------------


def test_missing_odbc_driver_fails_with_install_hint(fake_pyodbc: types.SimpleNamespace) -> None:
    fake_pyodbc.drivers = lambda: ["SQL Server", "ODBC Driver 17 for SQL Server"]
    with pytest.raises(FabricDriverError, match="ODBC Driver 18 for SQL Server"):
        FabricConnectionFactory(_credentials()).connect_lakehouse()
    assert fake_pyodbc.calls == []


def test_pyodbc_error_is_wrapped_with_sqlstate_only(fake_pyodbc: types.SimpleNamespace) -> None:
    def failing_connect(connstring: str, **kwargs: Any) -> object:
        raise FakePyodbcError("08001", "[08001] TCP Provider: host unknown")

    fake_pyodbc.connect = failing_connect
    with pytest.raises(FabricConnectionError) as excinfo:
        FabricConnectionFactory(_credentials()).connect_warehouse()
    message = str(excinfo.value)
    assert "08001" in message and "warehouse" in message
    assert TOKEN not in message and SECRET not in message


def test_token_failure_raises_auth_error(
    fake_pyodbc: types.SimpleNamespace, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(azure.identity, "ClientSecretCredential", FailingCredential)
    with pytest.raises(FabricAuthError, match="service_principal") as excinfo:
        FabricConnectionFactory(_credentials()).connect_lakehouse()
    assert "AADSTS" not in str(excinfo.value)
    assert fake_pyodbc.calls == []


# --- Secrets never leak ----------------------------------------------------------------


def test_secrets_and_token_never_reach_logs_or_repr(
    fake_pyodbc: types.SimpleNamespace, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.DEBUG)
    factory = FabricConnectionFactory(_credentials())
    factory.connect_lakehouse()
    factory.connect_warehouse()
    rendered = [repr(factory), str(factory), caplog.text]
    rendered += [str(r.__dict__) for r in caplog.records]
    for text in rendered:
        assert SECRET not in text
        assert TOKEN not in text
        assert "Driver={" not in text  # full connection strings are never logged
    assert any(getattr(r, "target", None) == "warehouse" for r in caplog.records)


# --- Lazy imports ----------------------------------------------------------------------


def test_module_imports_without_pyodbc_or_azure_identity() -> None:
    code = (
        "import sys\n"
        "sys.modules['pyodbc'] = None\n"
        "sys.modules['azure.identity'] = None\n"
        "import src.utils.fabric\n"
        "print('ok')\n"
    )
    result = subprocess.run(
        [sys.executable, "-c", code], cwd=PROJECT_ROOT, capture_output=True, text=True, check=False
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "ok"


def test_connect_without_pyodbc_raises_driver_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(sys.modules, "pyodbc", None)
    with pytest.raises(FabricDriverError, match="unixODBC"):
        FabricConnectionFactory(_credentials()).connect_lakehouse()


def test_missing_azure_identity_raises_auth_error(
    fake_pyodbc: types.SimpleNamespace, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setitem(sys.modules, "azure.identity", None)
    with pytest.raises(FabricAuthError, match="azure-identity"):
        FabricConnectionFactory(_credentials()).connect_lakehouse()


def test_module_exposes_documented_constants() -> None:
    assert fabric_module.ODBC_DRIVER == "ODBC Driver 18 for SQL Server"
    assert fabric_module.TDS_PORT == 1433
