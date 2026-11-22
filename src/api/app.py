"""FastAPI application: ``create_app`` wires routes, auth, errors and timeouts (S8, S17).

Routes (all but ``/health`` need ``X-API-Key``):

- ``GET  /health``                  state of the API, database and vector index (RF-26)
- ``POST /buscar_solucion``         cited answer from the knowledge base (RF-04, RF-05)
- ``POST /tickets``                 create a ticket, classified and redacted (RF-16, RF-10)
- ``GET  /tickets/{ticket_id}``     status of a ticket (RF-17)
- ``GET  /metricas``                metrics of an ``area`` or ``sucursal`` (RF-19)

Dependencies come in through ``ApiServices`` (answer service, ticket repository, index
probe), so tests inject fakes. Nothing here builds or refreshes the index: ``index`` is an
offline command and requests only read the version named by ``CURRENT`` (S7).

Every blocking call runs in a worker thread under ``api.request_timeout_s``; when it
expires the client gets 504 (the thread is abandoned, not killed, and its result is dropped).
"""

import logging
import threading
import time
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from functools import partial
from typing import Annotated, Any, Protocol, TypeVar

import anyio
import anyio.to_thread
from fastapi import APIRouter, Depends, FastAPI, Path, Query, Request

from src.api.errors import ApiError, install_error_handlers
from src.api.middleware import RequestContextMiddleware
from src.api.repository import (
    MetricScope,
    RepositoryUnavailableError,
    TicketRepository,
    build_repository,
)
from src.api.schemas import (
    TICKET_ID_PATTERN,
    AreaMetricsResponse,
    AreaName,
    BuscarSolucionRequest,
    BuscarSolucionResponse,
    CitationOut,
    CrearTicketRequest,
    CrearTicketResponse,
    ErrorResponse,
    HealthResponse,
    TicketStatusResponse,
    build_create_request,
    build_search_request,
)
from src.api.security import require_api_key
from src.api.ticket_service import TicketCreator, TicketService
from src.llm import NoLLM
from src.retrieval.answer_service import Answer, AnswerService
from src.utils.config import Settings
from src.utils.config import require_api_key as settings_api_key
from src.vectordb.chroma_store import IndexNotFoundError

logger = logging.getLogger(__name__)

API_TITLE = "DeskPilot AI"
API_VERSION = "0.1.0"
HEALTH_CACHE_S = 10.0
T = TypeVar("T")

_ERRORS: dict[int | str, dict[str, Any]] = {
    401: {"model": ErrorResponse, "description": "Missing or invalid X-API-Key."},
    422: {"model": ErrorResponse, "description": "The request is not valid."},
    500: {"model": ErrorResponse, "description": "Internal server error."},
    503: {"model": ErrorResponse, "description": "Database or vector index unavailable."},
    504: {"model": ErrorResponse, "description": "The request took too long."},
}
_TOO_LARGE: dict[int | str, dict[str, Any]] = {
    413: {"model": ErrorResponse, "description": "The request body is too large."},
}


class SearchService(Protocol):
    """What ``buscar_solucion`` needs; ``AnswerService`` implements it."""

    def answer(self, query: str, categoria: str | None = None) -> Answer: ...


IndexProbe = Callable[[], str | None]
"""Returns the index version when the index is usable; raises ``IndexNotFoundError`` if not."""


@dataclass
class ApiServices:
    """Everything the routes depend on, injectable for tests."""

    answers: SearchService
    repository: TicketRepository
    index_probe: IndexProbe
    mode: str = "local"
    tickets: TicketCreator | None = None
    closers: list[Callable[[], None]] = field(default_factory=list)

    def close(self) -> None:
        for close in self.closers:
            close()


def build_services(settings: Settings) -> ApiServices:
    """Real services for ``settings``: Chroma ``CurrentStore`` (read only), LLM, repository."""
    from src.embeddings.factory import build_embedder
    from src.llm.factory import build_llm
    from src.retrieval.reranker import build_reranker
    from src.retrieval.retriever import Retriever
    from src.vectordb.versions import CurrentStore

    store = CurrentStore.from_settings(settings)
    reranker = build_reranker(settings)
    if reranker is not None:
        reranker.warm()  # at start-up (fail fast), never inside a request
    retriever = Retriever.from_settings(settings, build_embedder(settings), store.get, reranker)
    llm = build_llm(settings)
    answers = AnswerService(retriever, llm, settings)
    repository = build_repository(settings)

    def probe() -> str | None:
        store.get()
        return store.version

    return ApiServices(
        answers=answers,
        repository=repository,
        index_probe=probe,
        mode=settings.app.mode,
        tickets=TicketService(repository, llm, settings),
        closers=[store.close],
    )


class _Runner:
    """Runs blocking work in a worker thread under the request timeout."""

    def __init__(self, timeout_s: float) -> None:
        self.timeout_s = timeout_s

    async def run(self, func: Callable[..., T], *args: Any) -> T:
        try:
            with anyio.fail_after(self.timeout_s):
                return await anyio.to_thread.run_sync(partial(func, *args), abandon_on_cancel=True)
        except TimeoutError:
            logger.warning("Request timed out", extra={"timeout_s": self.timeout_s})
            raise ApiError(504) from None


def _services(request: Request) -> ApiServices:
    services: ApiServices = request.app.state.services
    return services


def _runner(request: Request) -> _Runner:
    runner: _Runner = request.app.state.runner
    return runner


Services = Annotated[ApiServices, Depends(_services)]
Runner = Annotated[_Runner, Depends(_runner)]


def _to_response(answer: Answer) -> BuscarSolucionResponse:
    return BuscarSolucionResponse(
        status=answer.status,
        language=answer.language,
        text=answer.text,
        citations=[CitationOut(**c.model_dump()) for c in answer.citations],
        sensitive_data_warning=answer.sensitive_data_warning,
        mode=answer.mode,
    )


class _HealthProbe:
    """Cached, single-flight health check.

    Unauthenticated callers must not drive database traffic nor pile up worker
    threads: at most one probe runs at a time and every outcome (also a timeout)
    is cached for ``HEALTH_CACHE_S``.
    """

    def __init__(self) -> None:
        self._at = float("-inf")
        self._value: HealthResponse | None = None
        self._lock = threading.Lock()
        self._inflight = False

    async def get(self, runner: _Runner, services: ApiServices) -> HealthResponse:
        now = time.monotonic()
        if self._value is not None and now - self._at <= HEALTH_CACHE_S:
            return self._value
        with self._lock:
            if self._inflight:
                return self._value or _DEGRADED
            self._inflight = True
        try:
            value = await runner.run(self._check, services)
        except ApiError:
            value = _DEGRADED
        self._value = value
        self._at = time.monotonic()
        return value

    def _check(self, services: ApiServices) -> HealthResponse:
        try:
            return self._probe(services)
        finally:
            with self._lock:
                self._inflight = False

    @staticmethod
    def _probe(services: ApiServices) -> HealthResponse:
        try:
            database_ok = services.repository.ping()
        except Exception as exc:
            logger.error("Database ping failed", extra={"error": type(exc).__name__})
            database_ok = False
        try:
            services.index_probe()
            index_ok = True
        except IndexNotFoundError:
            index_ok = False
        except Exception as exc:
            logger.error("Index probe failed", extra={"error": type(exc).__name__})
            index_ok = False
        return HealthResponse(status="ok" if database_ok and index_ok else "degraded")


_DEGRADED = HealthResponse(status="degraded")


def _build_router(settings: Settings, api_key: str) -> APIRouter:
    search_model = build_search_request(settings.api.max_query_chars)
    create_model = build_create_request(settings.api.max_description_chars)
    router = APIRouter(dependencies=[Depends(require_api_key(api_key))], responses=_ERRORS)

    @router.post(
        "/buscar_solucion",
        operation_id="buscar_solucion",
        responses=_TOO_LARGE,
        summary="Search a cited solution in the knowledge base",
        response_model=BuscarSolucionResponse,
    )
    async def buscar_solucion(
        body: search_model,  # type: ignore[valid-type]
        services: Services,
        runner: Runner,
    ) -> BuscarSolucionResponse:
        request: BuscarSolucionRequest = body
        try:
            answer = await runner.run(services.answers.answer, request.query, request.categoria)
        except IndexNotFoundError:
            logger.error("Search without an index; run: python main.py index")
            raise ApiError(
                503, "index_unavailable", "The knowledge base index is not ready."
            ) from None
        return _to_response(answer)

    @router.post(
        "/tickets",
        operation_id="crear_ticket",
        responses=_TOO_LARGE,
        summary="Create a ticket, classified by category and priority",
        response_model=CrearTicketResponse,
        status_code=201,
    )
    async def crear_ticket(
        body: create_model,  # type: ignore[valid-type]
        services: Services,
        runner: Runner,
    ) -> CrearTicketResponse:
        request: CrearTicketRequest = body
        creator = services.tickets
        assert creator is not None
        try:
            return await runner.run(creator.create, request)
        except RepositoryUnavailableError:
            raise ApiError(
                503, "database_unavailable", "The ticket database is unavailable."
            ) from None

    @router.get(
        "/tickets/{ticket_id}",
        operation_id="consultar_estado_ticket",
        summary="Status of a ticket",
        response_model=TicketStatusResponse,
        responses={404: {"model": ErrorResponse, "description": "Ticket not found."}},
    )
    async def consultar_estado_ticket(
        ticket_id: Annotated[str, Path(pattern=TICKET_ID_PATTERN, description="Ticket id.")],
        services: Services,
        runner: Runner,
    ) -> TicketStatusResponse:
        try:
            status = await runner.run(services.repository.get_ticket_status, ticket_id)
        except RepositoryUnavailableError:
            raise ApiError(
                503, "database_unavailable", "The ticket database is unavailable."
            ) from None
        if status is None:
            raise ApiError(404, "ticket_not_found", "Ticket not found.")
        return status

    @router.get(
        "/metricas",
        operation_id="metricas_area",
        summary="Ticket metrics of an area or branch",
        response_model=AreaMetricsResponse,
        responses={404: {"model": ErrorResponse, "description": "No tickets for that name."}},
    )
    async def metricas_area(
        services: Services,
        runner: Runner,
        area: Annotated[AreaName | None, Query(description="Area name.")] = None,
        sucursal: Annotated[AreaName | None, Query(description="Branch name.")] = None,
    ) -> AreaMetricsResponse:
        if (area is None) == (sucursal is None):
            raise ApiError(422, "validation_error", "Provide exactly one of area or sucursal.")
        scope: MetricScope = "area" if area is not None else "sucursal"
        name = area if area is not None else sucursal
        assert name is not None
        try:
            metrics = await runner.run(services.repository.area_metrics, scope, name)
        except RepositoryUnavailableError:
            raise ApiError(
                503, "database_unavailable", "The ticket database is unavailable."
            ) from None
        if metrics is None:
            raise ApiError(404, "not_found", "No tickets found for that name.")
        return metrics

    return router


def create_app(settings: Settings, services: ApiServices | None = None) -> FastAPI:
    """Build the app; ``services`` defaults to the real ones for ``settings``.

    Needs ``DESKPILOT_API_KEY`` (at least 16 characters) and fails fast otherwise.
    Interactive docs and ``/openapi.json`` are off: the spec is exported with
    ``app.openapi()`` (``export-openapi``), not served to anonymous callers.
    """
    api_key = settings_api_key(settings).get_secret_value()
    resolved = services if services is not None else build_services(settings)
    if resolved.tickets is None:  # injected services without a creator: rules only
        resolved.tickets = TicketService(resolved.repository, NoLLM(), settings)

    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
        try:
            yield
        finally:
            resolved.close()

    app = FastAPI(
        title=API_TITLE,
        version=API_VERSION,
        description="Tools of the DeskPilot L1 service desk agent (synthetic data).",
        lifespan=lifespan,
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )
    app.state.services = resolved
    app.state.runner = _Runner(settings.api.request_timeout_s)
    probe = _HealthProbe()
    install_error_handlers(app)
    app.add_middleware(RequestContextMiddleware, max_body_bytes=settings.api.max_body_bytes)

    @app.get(
        "/health",
        operation_id="health",
        summary="Health of the API, database and vector index",
        response_model=HealthResponse,
        responses={500: _ERRORS[500]},
    )
    async def health(request: Request, runner: Runner) -> HealthResponse:
        return await probe.get(runner, _services(request))

    app.include_router(_build_router(settings, api_key))
    return app
