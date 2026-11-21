"""Connections to Microsoft Fabric with Microsoft Entra ID (S6, S16, RF-18).

In fabric mode the tickets are *read* from the SQL analytics endpoint of the lakehouse
(read-only: T-SQL can define and query objects but not modify data) and new tickets are
*written* to a Fabric Warehouse (``dbo.tickets_nuevos``), which supports DDL and DML.
Both are reached through their TDS endpoint ("SQL connection string") on port 1433.

Authentication (sources in docs/sources.md, section "Microsoft Fabric (T11)"):

- Fabric only accepts Microsoft Entra ID (no SQL authentication) and ODBC Driver 18+.
- A token is requested with azure-identity for ``SQL_TOKEN_SCOPE`` and handed to the
  driver through the pre-connect attribute ``SQL_COPT_SS_ACCESS_TOKEN`` (1256) as an
  ``ACCESSTOKEN`` struct: 4-byte little-endian length + the token in UTF-16-LE. With a
  token the connection string must not contain UID, PWD, Authentication or
  Trusted_Connection, so it carries no secret at all.
- Credential: ``ClientSecretCredential`` when the service principal variables are set
  (AZURE_TENANT_ID, AZURE_CLIENT_ID, AZURE_CLIENT_SECRET), otherwise
  ``DefaultAzureCredential`` (for example, the identity of ``az login``).

``pyodbc`` and ``azure.identity`` are imported lazily, inside the methods that need
them, so local mode and CI never require unixODBC or the ODBC driver. Nothing here logs
tokens, secrets or full connection strings.

⚠ Not verified against a real tenant (pending T30): the scope
``https://database.windows.net/.default`` comes from the Azure SQL resource that Fabric
documents for SQL connections; if a token is issued but rejected, Microsoft Entra
suggests trying the double-slash form (``https://database.windows.net//.default``).
"""

from __future__ import annotations

import logging
import re
import struct
from collections.abc import Mapping
from typing import TYPE_CHECKING, Literal

from src.utils.config import ConfigError, FabricCredentials, Settings

if TYPE_CHECKING:
    from azure.core.credentials import TokenCredential
    from pyodbc import Connection

logger = logging.getLogger(__name__)

ODBC_DRIVER = "ODBC Driver 18 for SQL Server"
TDS_PORT = 1433
# Pre-connect attribute defined in msodbcsql.h. Confirmed locally with Driver 18: passing
# it together with Authentication= fails with FA005 "Cannot use Access Token with ...".
SQL_COPT_SS_ACCESS_TOKEN = 1256
SQL_TOKEN_SCOPE = "https://database.windows.net/.default"
DEFAULT_TIMEOUT_S = 30

Target = Literal["lakehouse", "warehouse"]
AuthMode = Literal["service_principal", "default_credential"]

# Default variable names (.env.example); from_settings uses the names in config.yaml.
DEFAULT_ENV_NAMES: Mapping[str, str] = {
    "sql_endpoint": "FABRIC_SQL_ENDPOINT",
    "lakehouse_database": "FABRIC_LAKEHOUSE_DATABASE",
    "warehouse_endpoint": "FABRIC_WAREHOUSE_ENDPOINT",
    "warehouse_database": "FABRIC_WAREHOUSE_DATABASE",
}

_LABEL = r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?"
_HOST_RE = re.compile(rf"^(?=.{{1,253}}$){_LABEL}(?:\.{_LABEL})+$")
_FORBIDDEN_IN_DATABASE = frozenset(";{}=")


class FabricDriverError(RuntimeError):
    """pyodbc or the Microsoft ODBC Driver 18 for SQL Server is not available."""


class FabricAuthError(RuntimeError):
    """A Microsoft Entra token for Fabric could not be obtained."""


class FabricConnectionError(RuntimeError):
    """The driver could not open the connection (the message carries the SQLSTATE)."""


def build_connection_string(host: str, database: str, driver: str = ODBC_DRIVER) -> str:
    """DSN-less connection string for token authentication (no credentials inside)."""
    return (
        f"Driver={{{driver}}};Server=tcp:{host},{TDS_PORT};Database={database};"
        "Encrypt=yes;TrustServerCertificate=no;"
    )


def encode_access_token(token: str) -> bytes:
    """Pack ``token`` as the driver's ACCESSTOKEN: uint32 LE length + UTF-16-LE bytes."""
    data = token.encode("utf-16-le")
    return struct.pack("<I", len(data)) + data


def _validate_host(value: str, env_name: str) -> str:
    host = value.strip()
    if not _HOST_RE.match(host):
        raise ConfigError(
            f"{env_name} must be only the host copied from Fabric (item Settings > "
            "SQL connection string), for example <id>.datawarehouse.fabric.microsoft.com, "
            "without 'tcp:', port, scheme or ';'. The value is not shown on purpose."
        )
    return host


def _validate_database(value: str, env_name: str) -> str:
    database = value.strip()
    if not database or _FORBIDDEN_IN_DATABASE & set(database):
        raise ConfigError(
            f"{env_name} must be the item name (Initial Catalog), not empty and without "
            "the characters ; { } =. The value is not shown on purpose."
        )
    return database


class FabricConnectionFactory:
    """Opens read connections (lakehouse SQL endpoint) and write connections (Warehouse).

    Values are validated on construction (fail fast). The azure-identity credential is
    created on the first connection and reused; every connection gets a fresh token.
    """

    __slots__ = ("_credential", "_creds", "_targets", "timeout_s")

    def __init__(
        self,
        credentials: FabricCredentials,
        *,
        credential: TokenCredential | None = None,
        timeout_s: int = DEFAULT_TIMEOUT_S,
        env_names: Mapping[str, str] = DEFAULT_ENV_NAMES,
    ) -> None:
        self._creds = credentials
        self._credential = credential
        self.timeout_s = timeout_s
        self._targets: dict[Target, tuple[str, str]] = {
            "lakehouse": (
                _validate_host(credentials.sql_endpoint, env_names["sql_endpoint"]),
                _validate_database(credentials.lakehouse_database, env_names["lakehouse_database"]),
            ),
            "warehouse": (
                _validate_host(credentials.warehouse_endpoint, env_names["warehouse_endpoint"]),
                _validate_database(credentials.warehouse_database, env_names["warehouse_database"]),
            ),
        }

    @classmethod
    def from_settings(
        cls, settings: Settings, *, timeout_s: int = DEFAULT_TIMEOUT_S
    ) -> FabricConnectionFactory:
        """Build the factory from ``load_settings()``; fails if fabric mode is not active."""
        if settings.secrets.fabric is None:
            raise ConfigError(
                "Fabric connections need DESKPILOT_MODE=fabric and the FABRIC_* variables "
                "(see .env.example); the current mode is "
                f"'{settings.app.mode}'."
            )
        names = {
            field.removesuffix("_env"): name for field, name in settings.fabric.model_dump().items()
        }
        return cls(settings.secrets.fabric, env_names=names, timeout_s=timeout_s)

    @property
    def auth_mode(self) -> AuthMode:
        return "service_principal" if self._creds.uses_service_principal else "default_credential"

    def __repr__(self) -> str:
        databases = {target: db for target, (_, db) in self._targets.items()}
        return f"FabricConnectionFactory(auth={self.auth_mode!r}, databases={databases!r})"

    def connect_lakehouse(self) -> Connection:
        """Read-only connection to the SQL analytics endpoint of the lakehouse."""
        return self._connect("lakehouse")

    def connect_warehouse(self) -> Connection:
        """Read/write connection to the Warehouse (commit explicitly after INSERT)."""
        return self._connect("warehouse")

    def _get_credential(self) -> TokenCredential:
        if self._credential is None:
            try:
                from azure.identity import ClientSecretCredential, DefaultAzureCredential
            except ImportError as exc:
                raise FabricAuthError(
                    "azure-identity is not installed: pip install -r requirements.txt"
                ) from exc
            creds = self._creds
            if creds.client_secret is not None and creds.tenant_id and creds.client_id:
                self._credential = ClientSecretCredential(
                    tenant_id=creds.tenant_id,
                    client_id=creds.client_id,
                    client_secret=creds.client_secret.get_secret_value(),
                )
            else:
                self._credential = DefaultAzureCredential()
        return self._credential

    def _token_struct(self) -> bytes:
        try:
            token = self._get_credential().get_token(SQL_TOKEN_SCOPE).token
        except FabricAuthError:
            raise
        except Exception as exc:  # azure-identity raises several exception types
            raise FabricAuthError(
                f"Could not get a Microsoft Entra token for Fabric (auth={self.auth_mode}). "
                "Check the service principal values, or run `az login` for "
                "DefaultAzureCredential."
            ) from exc
        return encode_access_token(token)

    def _connect(self, target: Target) -> Connection:
        try:
            import pyodbc
        except ImportError as exc:
            raise FabricDriverError(
                "pyodbc could not be imported. Install requirements.txt; on Linux also "
                f"install unixODBC and the Microsoft {ODBC_DRIVER}."
            ) from exc
        if ODBC_DRIVER not in pyodbc.drivers():
            raise FabricDriverError(
                f"{ODBC_DRIVER} is not installed (Fabric supports only ODBC 18 or higher). "
                f"Drivers found: {', '.join(pyodbc.drivers()) or 'none'}."
            )
        host, database = self._targets[target]
        attrs = {SQL_COPT_SS_ACCESS_TOKEN: self._token_struct()}
        try:
            conn = pyodbc.connect(
                build_connection_string(host, database),
                attrs_before=attrs,
                timeout=self.timeout_s,
                autocommit=False,
            )
        except pyodbc.Error as exc:
            sqlstate = exc.args[0] if exc.args else "unknown"
            raise FabricConnectionError(
                f"Could not connect to the Fabric {target} '{database}' (SQLSTATE {sqlstate})."
            ) from exc
        logger.info(
            "fabric connection opened",
            extra={"target": target, "database": database, "auth": self.auth_mode},
        )
        return conn
