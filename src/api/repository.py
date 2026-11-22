"""Ticket data access behind one interface, local (SQLite) or fabric (S8, S17, RF-17/18/19).

``TicketRepository`` is what the routes depend on; tests use fakes. ``SqlTicketRepository``
runs the same qmark-style SQL on any DB-API connection, so one class serves SQLite and
Microsoft Fabric (T-SQL). Only the connection factories differ:

- local: SQLite opened read-only (``mode=ro``), one connection per call (thread-safe).
- fabric: tickets from the lakehouse SQL endpoint and new tickets from the Warehouse.

Every database failure becomes ``RepositoryUnavailableError``. Fabric errors can carry
connection details, so they are logged by type only, never with a traceback (T11 finding).
"""

from __future__ import annotations

import logging
import sqlite3
from collections.abc import Callable, Sequence
from contextlib import closing
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Literal, Protocol, runtime_checkable

from src.api.schemas import AreaMetricsResponse, CategoryCount, TicketStatusResponse
from src.ingestion.ticket_generator import DATE_FORMAT
from src.utils.config import Settings
from src.utils.fabric import FabricConnectionFactory

logger = logging.getLogger(__name__)

TOP_CATEGORIES = 3
MetricScope = Literal["area", "sucursal"]
# Column names come from this fixed map, never from user input.
_SCOPE_COLUMNS: dict[MetricScope, str] = {"area": "area", "sucursal": "sucursal"}


class RepositoryUnavailableError(RuntimeError):
    """The database cannot be reached or queried (the cause is already logged)."""


@runtime_checkable
class TicketRepository(Protocol):
    def get_ticket_status(self, ticket_id: str) -> TicketStatusResponse | None:
        """Status of one ticket, or None if the id does not exist."""
        ...

    def area_metrics(self, scope: MetricScope, name: str) -> AreaMetricsResponse | None:
        """Metrics of an area or branch, or None if it has no tickets."""
        ...

    def ping(self) -> bool:
        """True when the database answers a trivial query."""
        ...


class Cursor(Protocol):
    def execute(self, sql: str, params: Sequence[Any] = ..., /) -> Any: ...
    def fetchall(self) -> Sequence[Any]: ...
    def fetchone(self) -> Any: ...


class Connection(Protocol):
    def cursor(self) -> Cursor: ...
    def close(self) -> None: ...


@dataclass(frozen=True)
class TicketSource:
    """A connection factory and the table that holds tickets there."""

    connect: Callable[[], Connection]
    table: str


def _as_datetime(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    return datetime.strptime(str(value), DATE_FORMAT)


def _as_flag(value: Any) -> bool | None:
    return None if value is None else bool(value)


class SqlTicketRepository:
    """Queries over one or more ``TicketSource``; identical SQL for SQLite and T-SQL."""

    def __init__(self, sources: Sequence[TicketSource], *, backend: str) -> None:
        if not sources:
            raise ValueError("at least one ticket source is required")
        self._sources = tuple(sources)
        self._backend = backend

    def _fail(self, exc: Exception) -> RepositoryUnavailableError:
        # Type only and no traceback: driver errors may carry hosts or SQLSTATE details.
        logger.error(
            "Database query failed",
            extra={"backend": self._backend, "error": type(exc).__name__},
        )
        return RepositoryUnavailableError(self._backend)

    def get_ticket_status(self, ticket_id: str) -> TicketStatusResponse | None:
        try:
            for source in self._sources:
                row = self._fetch_ticket(source, ticket_id)
                if row is not None:
                    return self._status(row)
        except Exception as exc:
            raise self._fail(exc) from None
        return None

    @staticmethod
    def _fetch_ticket(source: TicketSource, ticket_id: str) -> Sequence[Any] | None:
        sql = (
            "SELECT ticket_id, estado, prioridad, fecha_apertura, fecha_cierre, "
            f"sla_horas, sla_cumplido FROM {source.table} WHERE ticket_id = ?"
        )
        with closing(source.connect()) as conn:
            cursor = conn.cursor()
            cursor.execute(sql, (ticket_id,))
            row: Sequence[Any] | None = cursor.fetchone()
        return row

    @staticmethod
    def _status(row: Sequence[Any]) -> TicketStatusResponse:
        opened = _as_datetime(row[3])
        assert opened is not None
        sla_hours = int(row[5])
        return TicketStatusResponse(
            ticket_id=str(row[0]),
            estado=row[1],
            prioridad=row[2],
            fecha_apertura=opened,
            fecha_cierre=_as_datetime(row[4]),
            sla_horas=sla_hours,
            fecha_limite_sla=opened + timedelta(hours=sla_hours),
            sla_cumplido=_as_flag(row[6]),
        )

    def area_metrics(self, scope: MetricScope, name: str) -> AreaMetricsResponse | None:
        # Metrics read the historical table (first source); new tickets have no outcome yet.
        column = _SCOPE_COLUMNS[scope]
        table = self._sources[0].table
        totals_sql = (
            "SELECT COUNT(*), COUNT(sla_cumplido), "
            "SUM(CASE WHEN sla_cumplido = 1 THEN 1 ELSE 0 END), AVG(horas_resolucion) "
            f"FROM {table} WHERE {column} = ?"
        )
        categories_sql = (
            f"SELECT categoria, COUNT(*) FROM {table} WHERE {column} = ? GROUP BY categoria"
        )
        try:
            with closing(self._sources[0].connect()) as conn:
                cursor = conn.cursor()
                cursor.execute(totals_sql, (name,))
                total, closed, met, avg_hours = cursor.fetchone()
                if not total:
                    return None
                cursor.execute(categories_sql, (name,))
                counts = [(str(cat), int(n)) for cat, n in cursor.fetchall()]
        except Exception as exc:
            raise self._fail(exc) from None
        counts.sort(key=lambda item: (-item[1], item[0]))
        return AreaMetricsResponse(
            scope=scope,
            name=name,
            total_tickets=int(total),
            closed_tickets=int(closed),
            sla_cumplido_pct=round(100.0 * int(met or 0) / int(closed), 1) if closed else None,
            avg_horas_resolucion=None if avg_hours is None else round(float(avg_hours), 1),
            top_categorias=[
                CategoryCount(categoria=c, tickets=n) for c, n in counts[:TOP_CATEGORIES]
            ],
        )

    def ping(self) -> bool:
        try:
            for source in self._sources:
                with closing(source.connect()) as conn:
                    cursor = conn.cursor()
                    cursor.execute(f"SELECT 1 FROM {source.table} WHERE 1 = 0")
                    cursor.fetchone()
        except Exception as exc:
            self._fail(exc)
            return False
        return True


def _readonly_sqlite(db_path: Path) -> Callable[[], Connection]:
    uri = f"{db_path.resolve().as_uri()}?mode=ro"

    def connect() -> Connection:
        conn = sqlite3.connect(uri, uri=True, timeout=5)
        conn.execute("PRAGMA query_only = ON")
        return conn

    return connect


def build_sqlite_repository(db_path: Path) -> SqlTicketRepository:
    """Local mode: tickets and tickets_nuevos in the same read-only SQLite file."""
    connect = _readonly_sqlite(db_path)
    sources = [TicketSource(connect, "tickets"), TicketSource(connect, "tickets_nuevos")]
    return SqlTicketRepository(sources, backend="sqlite")


def build_fabric_repository(
    factory: FabricConnectionFactory,
) -> SqlTicketRepository:
    """Fabric mode: tickets from the lakehouse endpoint, new tickets from the Warehouse."""
    sources = [
        TicketSource(factory.connect_lakehouse, "dbo.tickets"),
        TicketSource(factory.connect_warehouse, "dbo.tickets_nuevos"),
    ]
    return SqlTicketRepository(sources, backend="fabric")


def build_repository(settings: Settings) -> TicketRepository:
    """The repository for ``app.mode``; fabric mode needs the FABRIC_* variables."""
    if settings.app.mode == "fabric":
        factory = FabricConnectionFactory.from_settings(
            settings, timeout_s=int(settings.api.request_timeout_s)
        )
        return build_fabric_repository(factory)
    return build_sqlite_repository(settings.paths.sqlite_db)
