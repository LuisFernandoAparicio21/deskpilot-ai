"""``SqlTicketRepository`` with fake DB-API connections: Fabric failure handling (S8, S17, T11)."""

from __future__ import annotations

import logging
from collections.abc import Sequence
from datetime import datetime
from pathlib import Path
from typing import Any

import pytest

from src.api import RepositoryUnavailableError, SqlTicketRepository, TicketRepository
from src.api.repository import (
    TicketSource,
    build_fabric_repository,
    build_repository,
    build_sqlite_repository,
)
from src.utils.config import ConfigError, load_settings

LEAK = "Login failed for user 'svc' at secret-host.datawarehouse.fabric.microsoft.com"
TICKET_ROW = ("TCK-1", "cerrado", "P2", "2026-03-01 10:00:00", "2026-03-01 15:00:00", 8, 1)


class FakeCursor:
    def __init__(self, conn: FakeConnection) -> None:
        self.conn = conn
        self.rows: list[Sequence[Any]] = []

    def execute(self, sql: str, params: Sequence[Any] = (), /) -> None:
        self.conn.executed.append((sql, tuple(params)))
        if self.conn.error is not None:
            raise self.conn.error
        self.rows = list(self.conn.results.pop(0)) if self.conn.results else []

    def fetchone(self) -> Any:
        return self.rows[0] if self.rows else None

    def fetchall(self) -> Sequence[Any]:
        return self.rows


class FakeConnection:
    def __init__(self, results: list[list[Any]] | None = None, error: Exception | None = None):
        self.results = results or []
        self.error = error
        self.executed: list[tuple[str, tuple[Any, ...]]] = []
        self.closed = False

    def cursor(self) -> FakeCursor:
        return FakeCursor(self)

    def close(self) -> None:
        self.closed = True


def _repo(*conns: FakeConnection, tables: Sequence[str] = ("dbo.tickets", "dbo.tickets_nuevos")):
    sources = [TicketSource(lambda c=c: c, t) for c, t in zip(conns, tables, strict=False)]
    return SqlTicketRepository(sources, backend="fabric")


def test_sql_error_becomes_repository_unavailable_without_traceback_or_text(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.DEBUG)
    repo = _repo(FakeConnection(error=RuntimeError(LEAK)))
    with pytest.raises(RepositoryUnavailableError) as info:
        repo.get_ticket_status("TCK-1")
    assert "secret-host" not in str(info.value)
    assert info.value.__cause__ is None
    assert info.value.__suppress_context__ is True
    records = [r for r in caplog.records if r.name == "src.api.repository"]
    assert len(records) == 1
    assert records[0].exc_info is None
    assert records[0].exc_text is None
    assert records[0].__dict__["error"] == "RuntimeError"
    assert records[0].__dict__["backend"] == "fabric"
    assert "secret-host" not in caplog.text
    assert "svc" not in caplog.text


def test_connection_failure_is_also_wrapped(caplog: pytest.LogCaptureFixture) -> None:
    def boom() -> FakeConnection:
        raise OSError(LEAK)

    repo = SqlTicketRepository([TicketSource(boom, "dbo.tickets")], backend="fabric")
    with pytest.raises(RepositoryUnavailableError):
        repo.area_metrics("area", "Caja")
    assert repo.ping() is False
    assert "secret-host" not in caplog.text
    assert all(r.exc_info is None for r in caplog.records)


def test_area_metrics_failure_logs_type_only(caplog: pytest.LogCaptureFixture) -> None:
    repo = _repo(FakeConnection(error=ValueError(LEAK)))
    with pytest.raises(RepositoryUnavailableError):
        repo.area_metrics("sucursal", "Caja")
    assert [r.__dict__["error"] for r in caplog.records if r.name == "src.api.repository"] == [
        "ValueError"
    ]
    assert LEAK not in caplog.text


def test_ticket_is_found_in_the_second_source_and_connections_are_closed() -> None:
    lakehouse = FakeConnection(results=[[]])
    warehouse = FakeConnection(results=[[TICKET_ROW]])
    status = _repo(lakehouse, warehouse).get_ticket_status("TCK-1")
    assert status is not None
    assert status.estado == "cerrado"
    assert status.fecha_limite_sla == datetime(2026, 3, 1, 18, 0, 0)  # opened + 8 h
    assert status.sla_cumplido is True
    assert lakehouse.closed and warehouse.closed
    assert "FROM dbo.tickets WHERE" in lakehouse.executed[0][0]
    assert "FROM dbo.tickets_nuevos WHERE" in warehouse.executed[0][0]


def test_ticket_id_is_a_bound_parameter_never_part_of_the_sql() -> None:
    conn = FakeConnection(results=[[]])
    payload = "x'; DROP TABLE tickets;--"
    assert _repo(conn, FakeConnection(results=[[]])).get_ticket_status(payload) is None
    sql, params = conn.executed[0]
    assert payload not in sql
    assert params == (payload,)
    assert sql.count("?") == 1


def test_metrics_use_the_first_source_and_bind_the_name() -> None:
    totals = [(4, 2, 1, 6.26)]
    categories = [[("Hardware", 1), ("Accesos", 2), ("Software", 1)]]
    first = FakeConnection(results=[totals, *categories])
    second = FakeConnection()
    metrics = _repo(first, second).area_metrics("area", "x' OR '1'='1")
    assert second.executed == []
    assert all("x' OR" not in sql for sql, _ in first.executed)
    assert all(params == ("x' OR '1'='1",) for _, params in first.executed)
    assert metrics is not None
    assert (metrics.total_tickets, metrics.closed_tickets) == (4, 2)
    assert metrics.sla_cumplido_pct == 50.0
    assert metrics.avg_horas_resolucion == 6.3  # 6.26 rounded to one decimal
    assert [(c.categoria, c.tickets) for c in metrics.top_categorias] == [
        ("Accesos", 2), ("Hardware", 1), ("Software", 1),
    ]  # fmt: skip


def test_metrics_of_an_unknown_name_are_none() -> None:
    assert _repo(FakeConnection(results=[[(0, 0, None, None)]])).area_metrics("area", "x") is None


def test_metrics_without_closed_tickets_have_null_percent_and_average() -> None:
    conn = FakeConnection(results=[[(3, 0, None, None)], [("Accesos", 3)]])
    metrics = _repo(conn).area_metrics("sucursal", "Sur")
    assert metrics is not None
    assert metrics.sla_cumplido_pct is None
    assert metrics.avg_horas_resolucion is None
    assert metrics.closed_tickets == 0


def test_top_categories_are_limited_to_three_and_ties_sorted_by_name() -> None:
    cats = [("D", 5), ("C", 5), ("B", 5), ("A", 5), ("Z", 9)]
    conn = FakeConnection(results=[[(29, 0, None, None)], cats])
    metrics = _repo(conn).area_metrics("area", "x")
    assert metrics is not None
    assert [c.categoria for c in metrics.top_categorias] == ["Z", "A", "B"]


def test_ping_true_when_every_source_answers_and_false_when_one_fails() -> None:
    assert _repo(FakeConnection(), FakeConnection()).ping() is True
    assert _repo(FakeConnection(), FakeConnection(error=RuntimeError("x"))).ping() is False


def test_repository_needs_at_least_one_source() -> None:
    with pytest.raises(ValueError, match="at least one"):
        SqlTicketRepository([], backend="sqlite")


def test_sqlite_repository_on_a_missing_file_is_unavailable(tmp_path: Path) -> None:
    repo = build_sqlite_repository(tmp_path / "missing.db")
    assert isinstance(repo, TicketRepository)
    assert repo.ping() is False
    with pytest.raises(RepositoryUnavailableError):
        repo.get_ticket_status("TCK-1")
    with pytest.raises(RepositoryUnavailableError):
        repo.area_metrics("area", "Caja")
    assert not (tmp_path / "missing.db").exists()  # read-only open never creates the file


def test_fabric_repository_reads_tickets_from_lakehouse_and_new_ones_from_warehouse() -> None:
    class Factory:
        def __init__(self) -> None:
            self.calls: list[str] = []

        def connect_lakehouse(self) -> FakeConnection:
            self.calls.append("lakehouse")
            return FakeConnection(results=[[]])

        def connect_warehouse(self) -> FakeConnection:
            self.calls.append("warehouse")
            return FakeConnection(results=[[TICKET_ROW]])

    factory = Factory()
    repo = build_fabric_repository(factory)  # type: ignore[arg-type]
    assert repo.get_ticket_status("TCK-1") is not None
    assert factory.calls == ["lakehouse", "warehouse"]


def test_build_repository_picks_sqlite_in_local_mode(tmp_path: Path) -> None:
    settings = load_settings(env_file=tmp_path / "missing.env")
    paths = settings.paths.model_copy(update={"sqlite_db": tmp_path / "x.db"})
    repo = build_repository(settings.model_copy(update={"paths": paths}))
    assert isinstance(repo, SqlTicketRepository)


def test_build_repository_in_fabric_mode_without_credentials_fails_clearly(tmp_path: Path) -> None:
    settings = load_settings(env_file=tmp_path / "missing.env")
    fabric_mode = settings.model_copy(
        update={"app": settings.app.model_copy(update={"mode": "fabric"})}
    )
    with pytest.raises(ConfigError, match="FABRIC_"):
        build_repository(fabric_mode)
