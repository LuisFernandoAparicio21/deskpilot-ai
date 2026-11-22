"""``SqlTicketRepository.create_ticket`` with fake DB-API connections (S9, S17, RN-05)."""

from __future__ import annotations

import logging
import re
from collections.abc import Callable, Sequence
from datetime import datetime
from typing import Any

import pytest

from src.api.repository import (
    ID_ATTEMPTS,
    NewTicket,
    RepositoryUnavailableError,
    SqlTicketRepository,
    TicketSource,
    WriteTarget,
    build_fabric_repository,
)

LEAK = "Login failed for user 'svc' at secret-host.datawarehouse.fabric.microsoft.com"
TICKET = NewTicket(
    fecha_apertura=datetime(2026, 3, 2, 9, 30, 15),
    categoria="Conectividad",
    subcategoria="VPN",
    prioridad="P3",
    sucursal="Centro'; DROP TABLE x;--",
    area="Caja",
    canal="Teams",
    sla_horas=24,
    idioma="es",
    descripcion="La VPN falla'); DELETE FROM tickets_nuevos;--",
)


class Cursor:
    def __init__(self, conn: Conn) -> None:
        self.conn = conn
        self.row: Any = None

    def execute(self, sql: str, params: Sequence[Any] = (), /) -> None:
        self.conn.executed.append((sql, tuple(params)))
        if self.conn.error is not None:
            raise self.conn.error
        if sql.startswith("SELECT 1 FROM"):
            self.row = (1,) if params[0] in self.conn.taken else None

    def fetchone(self) -> Any:
        return self.row

    def fetchall(self) -> Sequence[Any]:
        return []


class Conn:
    def __init__(self, taken: set[str] | None = None, error: Exception | None = None) -> None:
        self.taken = taken or set()
        self.error = error
        self.executed: list[tuple[str, tuple[Any, ...]]] = []
        self.commits = 0
        self.rollbacks = 0
        self.closed = False

    def cursor(self) -> Cursor:
        return Cursor(self)

    def commit(self) -> None:
        self.commits += 1

    def rollback(self) -> None:
        self.rollbacks += 1

    def close(self) -> None:
        self.closed = True


def _repo(
    conn: Conn,
    ids: Callable[[], str],
    *,
    unique_in: tuple[str, ...] = ("dbo.tickets_nuevos",),
    begin_sql: str | None = None,
) -> SqlTicketRepository:
    target = WriteTarget(lambda: conn, "dbo.tickets_nuevos", unique_in, begin_sql)
    source = TicketSource(lambda: conn, "dbo.tickets")
    return SqlTicketRepository([source], backend="fabric", writer=target, id_factory=ids)


def _insert(conn: Conn) -> tuple[str, tuple[Any, ...]]:
    inserts = [e for e in conn.executed if e[0].startswith("INSERT")]
    assert len(inserts) == 1
    return inserts[0]


def test_insert_is_parameterized_and_user_text_is_never_in_the_sql() -> None:
    conn = Conn()
    ticket_id = _repo(conn, lambda: "TCK-123456").create_ticket(TICKET)
    sql, params = _insert(conn)
    assert ticket_id == "TCK-123456"
    assert sql.startswith("INSERT INTO dbo.tickets_nuevos (ticket_id,")
    assert (
        sql.count("?") == len(params) == 13
    )  # 18 columns; 5 are literals (NULLs and es_repetitivo = 0)
    for text in (TICKET.sucursal, TICKET.descripcion, TICKET.area, "DROP", "DELETE"):
        assert text not in sql
    assert TICKET.sucursal in params
    assert TICKET.descripcion in params
    assert params[0] == "TCK-123456"
    assert params[1] == "2026-03-02 09:30:15"
    assert "2026-03" in params


def test_every_execute_uses_placeholders_not_interpolated_values() -> None:
    conn = Conn()
    _repo(conn, lambda: "TCK-123456").create_ticket(TICKET)
    for sql, _ in conn.executed:
        assert "TCK-123456" not in sql
        assert "Centro" not in sql


def test_commit_closes_and_no_rollback_on_success() -> None:
    conn = Conn()
    _repo(conn, lambda: "TCK-123456").create_ticket(TICKET)
    assert (conn.commits, conn.rollbacks, conn.closed) == (1, 0, True)


def test_sqlite_style_write_lock_statement_runs_first() -> None:
    conn = Conn()
    _repo(conn, lambda: "TCK-123456", begin_sql="BEGIN IMMEDIATE").create_ticket(TICKET)
    assert conn.executed[0][0] == "BEGIN IMMEDIATE"


def test_taken_id_is_retried_with_a_new_one() -> None:
    conn = Conn(taken={"TCK-111111", "TCK-222222"})
    ids = iter(["TCK-111111", "TCK-222222", "TCK-333333"])
    assert _repo(conn, lambda: next(ids)).create_ticket(TICKET) == "TCK-333333"
    assert _insert(conn)[1][0] == "TCK-333333"


def test_id_must_be_free_in_every_unique_table() -> None:
    conn = Conn(taken={"TCK-111111"})
    ids = iter(["TCK-111111", "TCK-222222"])
    repo = _repo(conn, lambda: next(ids), unique_in=("dbo.tickets_nuevos", "dbo.tickets"))
    assert repo.create_ticket(TICKET) == "TCK-222222"
    checked = [sql for sql, _ in conn.executed if sql.startswith("SELECT 1")]
    assert any("dbo.tickets WHERE" in sql for sql in checked)


def test_exhausted_id_attempts_fail_without_inserting() -> None:
    conn = Conn(taken={"TCK-111111"})
    with pytest.raises(RepositoryUnavailableError):
        _repo(conn, lambda: "TCK-111111").create_ticket(TICKET)
    assert not [e for e in conn.executed if e[0].startswith("INSERT")]
    assert conn.rollbacks == 1
    assert len([e for e in conn.executed if e[0].startswith("SELECT 1")]) == ID_ATTEMPTS


def test_fabric_error_is_unavailable_logged_by_type_without_traceback_or_text(
    caplog: pytest.LogCaptureFixture,
) -> None:
    conn = Conn(error=RuntimeError(LEAK))
    with caplog.at_level(logging.DEBUG), pytest.raises(RepositoryUnavailableError) as info:
        _repo(conn, lambda: "TCK-123456").create_ticket(TICKET)
    assert LEAK not in str(info.value)
    assert info.value.__cause__ is None
    assert info.value.__suppress_context__ is True
    assert (conn.rollbacks, conn.closed) == (1, True)
    records = [r for r in caplog.records if r.name == "src.api.repository"]
    assert records
    for record in records:
        assert record.exc_info is None
        assert record.exc_text is None
        assert record.__dict__["error"] == "RuntimeError"
    logged = " ".join(f"{r.getMessage()} {r.__dict__}" for r in records)
    assert "secret-host" not in logged
    assert TICKET.descripcion not in logged


def test_commit_failure_rolls_back_and_is_unavailable() -> None:
    conn = Conn()

    def boom() -> None:
        raise OSError(LEAK)

    conn.commit = boom  # type: ignore[method-assign]
    with pytest.raises(RepositoryUnavailableError):
        _repo(conn, lambda: "TCK-123456").create_ticket(TICKET)
    assert conn.rollbacks == 1


def test_connect_failure_is_unavailable() -> None:
    def refuse() -> Conn:
        raise ConnectionError(LEAK)

    target = WriteTarget(refuse, "dbo.tickets_nuevos", ("dbo.tickets_nuevos",))
    repo = SqlTicketRepository(
        [TicketSource(lambda: Conn(), "dbo.tickets")], backend="fabric", writer=target
    )
    with pytest.raises(RepositoryUnavailableError):
        repo.create_ticket(TICKET)


def test_without_a_write_target_creating_is_unavailable() -> None:
    repo = SqlTicketRepository([TicketSource(lambda: Conn(), "dbo.tickets")], backend="fabric")
    with pytest.raises(RepositoryUnavailableError):
        repo.create_ticket(TICKET)


def test_default_ids_have_the_tck_format_and_are_not_sequential() -> None:
    conn = Conn()
    repo = SqlTicketRepository(
        [TicketSource(lambda: conn, "t")],
        backend="fabric",
        writer=WriteTarget(lambda: conn, "t", ("t",)),
    )
    ids = [repo.create_ticket(TICKET) for _ in range(30)]
    assert all(re.fullmatch(r"TCK-[1-9]\d{5}", i) for i in ids)
    assert ids != sorted(ids)  # random, not a counter (chance of 30 sorted draws: 1/30!)


def test_fabric_builder_writes_to_the_warehouse_table() -> None:
    calls: list[str] = []

    class Factory:
        def connect_warehouse(self) -> Conn:
            calls.append("warehouse")
            return Conn()

        def connect_lakehouse(self) -> Conn:
            calls.append("lakehouse")
            return Conn()

    repo = build_fabric_repository(Factory())  # type: ignore[arg-type]
    repo.create_ticket(TICKET)
    assert calls and set(calls) == {"warehouse"}
