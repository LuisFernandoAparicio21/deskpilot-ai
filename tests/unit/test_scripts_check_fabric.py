"""Behavior tests for scripts/check_fabric.py (S18, T25): exit codes, help text, no secrets.

Nothing here touches the network: pyodbc, the Entra credentials, the connection factory
and the repository are replaced by fakes that record their calls.
"""

from __future__ import annotations

import os
import sys
import types
from pathlib import Path
from typing import Any

import azure.identity
import pytest
from azure.core.credentials import AccessToken
from azure.core.exceptions import ClientAuthenticationError

import src.utils.config as config_module
from scripts import check_fabric
from src.api.repository import NewTicket
from src.utils.fabric import ODBC_DRIVER, FabricConnectionFactory

SECRET = "super-secret-client-value-9f3a"
TOKEN = "eyJhbGciOiJSUzI1NiJ9.token-payload-xyz.signature-abc"
SQL_HOST = "abc123.datawarehouse.fabric.microsoft.com"
WH_HOST = "def456.datawarehouse.fabric.microsoft.com"
CONNSTRING_MARKER = "Server=tcp:leaky-host,1433;PWD=leaky-password"
VARIABLES = {
    "FABRIC_SQL_ENDPOINT": SQL_HOST,
    "FABRIC_LAKEHOUSE_DATABASE": "lh_deskpilot",
    "FABRIC_WAREHOUSE_ENDPOINT": WH_HOST,
    "FABRIC_WAREHOUSE_DATABASE": "wh_deskpilot",
}
SP_VARIABLES = {
    "AZURE_TENANT_ID": "00000000-0000-0000-0000-000000000000",
    "AZURE_CLIENT_ID": "11111111-1111-1111-1111-111111111111",
    "AZURE_CLIENT_SECRET": SECRET,
}
ALL_NAMES = [*VARIABLES, *SP_VARIABLES, "DESKPILOT_MODE"]


@pytest.fixture(autouse=True)
def clean_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """No real .env and none of the FABRIC_* / AZURE_* variables."""
    missing = tmp_path / "no.env"
    monkeypatch.setattr(config_module, "DEFAULT_ENV_FILE", missing)
    monkeypatch.setattr(check_fabric, "DEFAULT_ENV_FILE", missing)
    for name in ALL_NAMES:
        # setenv first so monkeypatch restores the original state at teardown even though
        # check_fabric.main() writes os.environ["DESKPILOT_MODE"] directly.
        monkeypatch.setenv(name, "")
        monkeypatch.delenv(name)


def _set(monkeypatch: pytest.MonkeyPatch, values: dict[str, str]) -> None:
    for key, value in values.items():
        monkeypatch.setenv(key, value)


def _assert_clean(capsys: pytest.CaptureFixture[str]) -> str:
    captured = capsys.readouterr()
    text = captured.out + captured.err
    assert "Traceback" not in text
    for forbidden in (SECRET, TOKEN, CONNSTRING_MARKER, "PWD="):
        assert forbidden not in text
    return text


# --- Step 1: variables -----------------------------------------------------------------


def test_no_variables_exits_2_without_traceback_or_secrets(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert check_fabric.main([]) == check_fabric.EXIT_CONFIG == 2
    text = _assert_clean(capsys)
    for name in VARIABLES:
        assert f"{name}: MISSING" in text
    assert "Missing variables" in text


def test_partial_service_principal_is_a_config_error(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    _set(monkeypatch, VARIABLES)
    monkeypatch.setenv("AZURE_CLIENT_SECRET", SECRET)  # tenant and client id missing
    assert check_fabric.main([]) == 2
    text = _assert_clean(capsys)
    assert "AZURE_TENANT_ID" in text and "AZURE_CLIENT_ID" in text


def test_invalid_host_value_is_exit_2_not_a_crash(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    _set(monkeypatch, VARIABLES | {"FABRIC_SQL_ENDPOINT": "not a host; DROP TABLE"})
    assert check_fabric.main([]) == 2
    _assert_clean(capsys)


# --- Step 2/3: ODBC driver and token ----------------------------------------------------


def _fake_pyodbc(monkeypatch: pytest.MonkeyPatch, drivers: list[str]) -> None:
    module = types.SimpleNamespace(
        Error=type("Error", (Exception,), {}),
        drivers=lambda: drivers,
        connect=lambda *a, **k: pytest.fail("must not connect"),
    )
    monkeypatch.setitem(sys.modules, "pyodbc", module)


def test_variables_without_odbc_driver_exits_1_with_help(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    _set(monkeypatch, VARIABLES | SP_VARIABLES)
    _fake_pyodbc(monkeypatch, ["SQL Server"])
    assert check_fabric.main([]) == check_fabric.EXIT_CHECK_FAILED == 1
    text = _assert_clean(capsys)
    assert f"{ODBC_DRIVER} not installed" in text
    assert "Qué hacer:" in text and "aka.ms/downloadmsodbcsql" in text
    assert "SQL Server" in text  # lists what it did find


def test_token_failure_exits_1_with_help_and_no_secret(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    _set(monkeypatch, VARIABLES | SP_VARIABLES)
    _fake_pyodbc(monkeypatch, [ODBC_DRIVER])

    class Failing:
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            pass

        def get_token(self, *scopes: str, **kwargs: Any) -> AccessToken:
            raise ClientAuthenticationError(message=f"AADSTS7000215 bad secret {SECRET}")

    monkeypatch.setattr(azure.identity, "ClientSecretCredential", Failing)
    assert check_fabric.main([]) == 1
    text = _assert_clean(capsys)
    assert "Microsoft Entra token" in text
    assert "az login" in text and "Qué hacer:" in text


# --- Steps 4-6 with a simulated factory ------------------------------------------------


class FakePyodbcError(Exception):
    """Mimics pyodbc.Error: args[0] is the SQLSTATE, args[1] the (sensitive) message."""

    def __init__(self) -> None:
        super().__init__("28000", f"{CONNSTRING_MARKER} token={TOKEN}")


class FakeCursor:
    def __init__(self, conn: FakeConn) -> None:
        self.conn = conn

    def execute(self, sql: str, params: tuple[Any, ...] = ()) -> None:
        self.conn.executed.append((sql, params))
        if self.conn.fail_on and sql.startswith(self.conn.fail_on):
            raise FakePyodbcError()

    def fetchone(self) -> tuple[int]:
        return (7,)


class FakeConn:
    def __init__(self, log: list[tuple[str, tuple[Any, ...]]], fail_on: str = "") -> None:
        self.executed = log
        self.fail_on = fail_on
        self.commits = 0
        self.closed = False

    def cursor(self) -> FakeCursor:
        return FakeCursor(self)

    def commit(self) -> None:
        self.commits += 1

    def close(self) -> None:
        self.closed = True


class FakeFactory:
    auth_mode = "default_credential"

    def __init__(self, *, fail_on: str = "", fail_lakehouse: bool = False) -> None:
        self.log: list[tuple[str, tuple[Any, ...]]] = []
        self.fail_on = fail_on
        self.fail_lakehouse = fail_lakehouse
        self.connections: list[FakeConn] = []

    def _token_struct(self) -> bytes:
        return b"token"

    def connect_lakehouse(self) -> FakeConn:
        if self.fail_lakehouse:
            raise FakePyodbcError()
        return self._new("")

    def connect_warehouse(self) -> FakeConn:
        return self._new(self.fail_on)

    def _new(self, fail_on: str) -> FakeConn:
        conn = FakeConn(self.log, fail_on)
        self.connections.append(conn)
        return conn


class FakeRepository:
    def __init__(self, fail: bool = False) -> None:
        self.created: list[NewTicket] = []
        self.fail = fail

    def create_ticket(self, ticket: NewTicket) -> str:
        if self.fail:
            raise FakePyodbcError()
        self.created.append(ticket)
        return "TCK-TEST-0001"


def _wire(
    monkeypatch: pytest.MonkeyPatch, factory: FakeFactory, repo: FakeRepository | None = None
) -> FakeRepository:
    repository = repo or FakeRepository()
    _set(monkeypatch, VARIABLES)
    _fake_pyodbc(monkeypatch, [ODBC_DRIVER])
    monkeypatch.setattr(FabricConnectionFactory, "from_settings", lambda *a, **k: factory)
    monkeypatch.setattr(check_fabric, "build_fabric_repository", lambda f: repository)
    return repository


def test_read_only_run_passes_and_does_not_write(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    factory = FakeFactory()
    repo = _wire(monkeypatch, factory)
    assert check_fabric.main([]) == 0
    text = _assert_clean(capsys)
    assert "dbo.tickets has 7 rows" in text
    assert "write test skipped" in text
    assert repo.created == []
    assert not any(sql.startswith("DELETE") for sql, _ in factory.log)
    assert all(conn.closed for conn in factory.connections)


def test_write_test_inserts_then_deletes_the_same_ticket(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    factory = FakeFactory()
    repo = _wire(monkeypatch, factory)
    assert check_fabric.main(["--write-test"]) == 0
    text = _assert_clean(capsys)
    assert len(repo.created) == 1
    assert repo.created[0].descripcion == check_fabric.TEST_TICKET_TEXT
    deletes = [(sql, p) for sql, p in factory.log if sql.startswith("DELETE")]
    assert deletes == [("DELETE FROM dbo.tickets_nuevos WHERE ticket_id = ?", ("TCK-TEST-0001",))]
    delete_conn = next(c for c in factory.connections if c.commits)
    assert delete_conn.commits == 1 and delete_conn.closed
    assert "TCK-TEST-0001 inserted" in text and "TCK-TEST-0001 deleted" in text


def test_failed_delete_prints_the_manual_command_and_exits_1(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    factory = FakeFactory(fail_on="DELETE")
    _wire(monkeypatch, factory)
    assert check_fabric.main(["--write-test"]) == 1
    text = _assert_clean(capsys)
    assert "DELETE FROM dbo.tickets_nuevos WHERE ticket_id = 'TCK-TEST-0001'" in text
    assert "Could not delete test ticket TCK-TEST-0001" in text
    assert "deleted" not in text.replace("Could not delete", "")


def test_failed_insert_exits_1_and_does_not_try_to_delete(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    factory = FakeFactory()
    _wire(monkeypatch, factory, FakeRepository(fail=True))
    assert check_fabric.main(["--write-test"]) == 1
    text = _assert_clean(capsys)
    assert "Insert into dbo.tickets_nuevos: FakePyodbcError (SQLSTATE 28000)" in text
    assert not any(sql.startswith("DELETE") for sql, _ in factory.log)


def test_lakehouse_error_hides_connection_details(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    _wire(monkeypatch, FakeFactory(fail_lakehouse=True))
    assert check_fabric.main([]) == 1
    text = _assert_clean(capsys)
    assert "FakePyodbcError (SQLSTATE 28000)" in text and "FAILED" in text


def test_warehouse_error_skips_the_write_test(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    factory = FakeFactory(fail_on="SELECT COUNT(*) FROM dbo.tickets_nuevos")
    repo = _wire(monkeypatch, factory)
    assert check_fabric.main(["--write-test"]) == 1
    _assert_clean(capsys)
    assert repo.created == []


def test_invalid_option_exits_2() -> None:
    with pytest.raises(SystemExit) as info:
        check_fabric.main(["--bogus"])
    assert info.value.code == 2


def test_generic_exception_message_is_not_printed(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    factory = FakeFactory()

    def boom() -> FakeConn:
        raise RuntimeError(f"{CONNSTRING_MARKER} token={TOKEN}")

    factory.connect_lakehouse = boom  # type: ignore[method-assign]
    _wire(monkeypatch, factory)
    assert check_fabric.main([]) == 1
    _assert_clean(capsys)


JWT = "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTYifQ.c2lnbmF0dXJl"


@pytest.mark.parametrize(
    ("args", "expected"),
    [
        (("28000", f"{CONNSTRING_MARKER} token={TOKEN}"), "FakePyodbcError (SQLSTATE 28000)"),
        (("HY000",), "FakePyodbcError (SQLSTATE HY000)"),
        (("08S01", "Server=a;PWD=secret"), "FakePyodbcError (SQLSTATE 08S01)"),
        (("Server=tcp:h,1433;PWD=secret",), "FakePyodbcError"),
        ((JWT,), "FakePyodbcError"),
        (("28000;Server=h;PWD=secret",), "FakePyodbcError"),
        (("28000\n",), "FakePyodbcError"),
        (("2800",), "FakePyodbcError"),
        (("280000",), "FakePyodbcError"),
        (("28 00",), "FakePyodbcError"),
        (("ab123",), "FakePyodbcError"),
        ((28000, "Server=a;PWD=secret"), "FakePyodbcError"),
        ((), "FakePyodbcError"),
    ],
    ids=[
        "sqlstate-numeric-secret-in-args1",
        "sqlstate-alnum",
        "sqlstate-with-letter-and-digit",
        "connection-string-as-args0",
        "jwt-as-args0",
        "sqlstate-plus-suffix",
        "sqlstate-trailing-newline",
        "four-chars",
        "six-chars",
        "space-inside",
        "lowercase",
        "non-str-args0",
        "no-args",
    ],
)
def test_describe_emits_only_type_and_five_char_sqlstate(
    args: tuple[Any, ...], expected: str
) -> None:
    exc = FakePyodbcError()
    exc.args = args
    result = check_fabric.describe(exc)
    assert result == expected
    for forbidden in ("Server=", "PWD=", "secret", JWT, TOKEN, "eyJ"):
        assert forbidden not in result


def test_describe_generic_exception_with_secrets_is_type_only() -> None:
    exc = RuntimeError(f"{CONNSTRING_MARKER};PWD=secret token={JWT}")
    assert check_fabric.describe(exc) == "RuntimeError"


# --- DESKPILOT_MODE is always restored -------------------------------------------------


def _spy_load_settings(
    monkeypatch: pytest.MonkeyPatch, seen: list[str | None], error: Exception | None = None
) -> None:
    def spy() -> Any:
        seen.append(os.environ.get("DESKPILOT_MODE"))
        if error is not None:
            raise error
        return config_module.load_settings()

    monkeypatch.setattr(check_fabric, "load_settings", spy)


@pytest.mark.parametrize(
    "previous", [None, "local", "fabric", ""], ids=["unset", "local", "fabric", "empty"]
)
def test_deskpilot_mode_is_fabric_during_load_and_restored_after_main(
    monkeypatch: pytest.MonkeyPatch, previous: str | None
) -> None:
    if previous is not None:
        monkeypatch.setenv("DESKPILOT_MODE", previous)
    seen: list[str | None] = []
    _spy_load_settings(monkeypatch, seen)
    _wire(monkeypatch, FakeFactory())
    assert check_fabric.main([]) == 0
    assert seen == ["fabric"]
    assert os.environ.get("DESKPILOT_MODE") == previous


@pytest.mark.parametrize("previous", [None, "local"], ids=["unset", "local"])
def test_deskpilot_mode_is_restored_when_load_settings_raises(
    monkeypatch: pytest.MonkeyPatch, previous: str | None
) -> None:
    if previous is not None:
        monkeypatch.setenv("DESKPILOT_MODE", previous)
    seen: list[str | None] = []
    _spy_load_settings(monkeypatch, seen, RuntimeError("boom"))
    _wire(monkeypatch, FakeFactory())
    with pytest.raises(RuntimeError, match="boom"):
        check_fabric.main([])
    assert seen == ["fabric"]
    assert os.environ.get("DESKPILOT_MODE") == previous


@pytest.mark.parametrize("previous", [None, "local"], ids=["unset", "local"])
def test_deskpilot_mode_is_restored_on_config_error(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], previous: str | None
) -> None:
    if previous is not None:
        monkeypatch.setenv("DESKPILOT_MODE", previous)
    seen: list[str | None] = []
    _spy_load_settings(monkeypatch, seen, config_module.ConfigError("bad config"))
    _wire(monkeypatch, FakeFactory())
    assert check_fabric.main([]) == 2
    _assert_clean(capsys)
    assert seen == ["fabric"]
    assert os.environ.get("DESKPILOT_MODE") == previous
