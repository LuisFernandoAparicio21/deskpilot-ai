"""Ticket data access behind one interface, local (SQLite) or fabric (S8, S17, RF-17/18/19).

``TicketRepository`` is what the routes depend on; tests use fakes. ``SqlTicketRepository``
runs the same qmark-style SQL on any DB-API connection, so one class serves SQLite and
Microsoft Fabric (T-SQL). Only the connection factories differ:

- local: SQLite opened read-only (``mode=ro``), one connection per call (thread-safe).
  New tickets use a separate writable connection (``mode=rw``, never creates the file).
- fabric: tickets from the lakehouse SQL endpoint; new tickets are read from and written
  to the Warehouse (parametrized INSERT).

Every database failure becomes ``RepositoryUnavailableError``. Fabric errors can carry
connection details, so they are logged by type only, never with a traceback (T11 finding).
"""

from __future__ import annotations

import logging
import secrets
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
# New ids are random in TICKET_ID_MIN..TICKET_ID_MAX: above any generated historical id
# (config caps data.n_tickets at 50,000) and not guessable in sequence. Capacity: 900,000.
TICKET_ID_MIN = 100_000
TICKET_ID_MAX = 999_999
ID_ATTEMPTS = 8
NEW_TICKET_ESTADO = "abierto"
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

    def create_ticket(self, ticket: NewTicket) -> str:
        """Store a new ticket under a fresh server-generated id and return that id."""
        ...

    def ping(self) -> bool:
        """True when the database answers a trivial query."""
        ...


@dataclass(frozen=True)
class NewTicket:
    """A validated, classified and redacted ticket; the repository adds ``ticket_id``."""

    fecha_apertura: datetime
    categoria: str
    subcategoria: str
    prioridad: str
    sucursal: str
    area: str
    canal: str
    sla_horas: int
    idioma: str
    descripcion: str


class Cursor(Protocol):
    def execute(self, sql: str, params: Sequence[Any] = ..., /) -> Any: ...
    def fetchall(self) -> Sequence[Any]: ...
    def fetchone(self) -> Any: ...


class Connection(Protocol):
    def cursor(self) -> Cursor: ...
    def commit(self) -> None: ...
    def rollback(self) -> None: ...
    def close(self) -> None: ...


@dataclass(frozen=True)
class TicketSource:
    """A connection factory and the table that holds tickets there."""

    connect: Callable[[], Connection]
    table: str


@dataclass(frozen=True)
class WriteTarget:
    """Where new tickets are written: a writable connection factory and the tables to check.

    ``begin_sql`` starts an exclusive write transaction when the database needs one
    (SQLite ``BEGIN IMMEDIATE``); ``unique_in`` lists every table the new id must be
    absent from before inserting into ``table``.
    """

    connect: Callable[[], Connection]
    table: str
    unique_in: tuple[str, ...]
    begin_sql: str | None = None


def _new_ticket_id() -> str:
    return f"TCK-{TICKET_ID_MIN + secrets.randbelow(TICKET_ID_MAX - TICKET_ID_MIN + 1):06d}"


_INSERT_COLUMNS = (
    "ticket_id, fecha_apertura, fecha_cierre, categoria, subcategoria, prioridad, sucursal, "
    "area, canal, sla_horas, sla_cumplido, horas_resolucion, anio_mes, solucion, "
    "es_repetitivo, idioma, estado, descripcion"
)


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

    def __init__(
        self,
        sources: Sequence[TicketSource],
        *,
        backend: str,
        writer: WriteTarget | None = None,
        id_factory: Callable[[], str] = _new_ticket_id,
    ) -> None:
        if not sources:
            raise ValueError("at least one ticket source is required")
        self._sources = tuple(sources)
        self._backend = backend
        self._writer = writer
        self._id_factory = id_factory

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

    def create_ticket(self, ticket: NewTicket) -> str:
        """INSERT one ticket with a parametrized statement; returns the new ``ticket_id``.

        The id is generated here and checked to be unused inside the same transaction
        (SQLite takes the write lock first). Warehouse primary keys are NOT ENFORCED, so
        this check is the only guard; with several API instances the residual collision
        chance is about 1 in 900,000 per concurrent pair.
        """
        if self._writer is None:
            raise self._fail(RuntimeError("no write target"))
        try:
            return self._insert(self._writer, ticket)
        except Exception as exc:
            raise self._fail(exc) from None

    def _insert(self, target: WriteTarget, ticket: NewTicket) -> str:
        opened = ticket.fecha_apertura.strftime(DATE_FORMAT)
        with closing(target.connect()) as conn:
            try:
                cursor = conn.cursor()
                if target.begin_sql:
                    cursor.execute(target.begin_sql)
                ticket_id = self._free_id(cursor, target)
                cursor.execute(
                    f"INSERT INTO {target.table} ({_INSERT_COLUMNS}) "
                    "VALUES (?, ?, NULL, ?, ?, ?, ?, ?, ?, ?, NULL, NULL, ?, NULL, 0, ?, ?, ?)",
                    (
                        ticket_id,
                        opened,
                        ticket.categoria,
                        ticket.subcategoria,
                        ticket.prioridad,
                        ticket.sucursal,
                        ticket.area,
                        ticket.canal,
                        ticket.sla_horas,
                        ticket.fecha_apertura.strftime("%Y-%m"),
                        ticket.idioma,
                        NEW_TICKET_ESTADO,
                        ticket.descripcion,
                    ),
                )
                conn.commit()
            except BaseException:
                conn.rollback()
                raise
        return ticket_id

    def _free_id(self, cursor: Cursor, target: WriteTarget) -> str:
        for _ in range(ID_ATTEMPTS):
            candidate = self._id_factory()
            taken = False
            for table in target.unique_in:
                cursor.execute(f"SELECT 1 FROM {table} WHERE ticket_id = ?", (candidate,))
                if cursor.fetchone() is not None:
                    taken = True
                    break
            if not taken:
                return candidate
        raise RuntimeError("no free ticket id")

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


def _writable_sqlite(db_path: Path) -> Callable[[], Connection]:
    """Separate from the read-only factory: existing file only, used for tickets_nuevos."""
    uri = f"{db_path.resolve().as_uri()}?mode=rw"

    def connect() -> Connection:
        return sqlite3.connect(uri, uri=True, timeout=5)

    return connect


def build_sqlite_repository(db_path: Path) -> SqlTicketRepository:
    """Local mode: reads are read-only; new tickets go through a writable connection."""
    connect = _readonly_sqlite(db_path)
    sources = [TicketSource(connect, "tickets"), TicketSource(connect, "tickets_nuevos")]
    writer = WriteTarget(
        _writable_sqlite(db_path),
        "tickets_nuevos",
        unique_in=("tickets_nuevos", "tickets"),
        begin_sql="BEGIN IMMEDIATE",
    )
    return SqlTicketRepository(sources, backend="sqlite", writer=writer)


def build_fabric_repository(
    factory: FabricConnectionFactory,
) -> SqlTicketRepository:
    """Fabric mode: tickets from the lakehouse endpoint, new tickets from the Warehouse."""
    sources = [
        TicketSource(factory.connect_lakehouse, "dbo.tickets"),
        TicketSource(factory.connect_warehouse, "dbo.tickets_nuevos"),
    ]
    writer = WriteTarget(
        factory.connect_warehouse, "dbo.tickets_nuevos", unique_in=("dbo.tickets_nuevos",)
    )
    return SqlTicketRepository(sources, backend="fabric", writer=writer)


def build_repository(settings: Settings) -> TicketRepository:
    """The repository for ``app.mode``; fabric mode needs the FABRIC_* variables."""
    if settings.app.mode == "fabric":
        factory = FabricConnectionFactory.from_settings(
            settings, timeout_s=int(settings.api.request_timeout_s)
        )
        return build_fabric_repository(factory)
    return build_sqlite_repository(settings.paths.sqlite_db)
