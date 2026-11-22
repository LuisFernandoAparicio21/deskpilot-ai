"""MCP server exposing the four DeskPilot tools over the same service layer as the REST API (S10).

Tools: ``buscar_solucion``, ``consultar_estado_ticket``, ``metricas_area``, ``crear_ticket``.
Each one validates with the REST request models, calls ``ApiServices`` (``AnswerService``,
``TicketRepository``, ``TicketService``) and returns the REST response models, so limits,
redaction and classification are the ones of the API; nothing is duplicated.

Errors reach the client as ``ToolError`` with a fixed message: never exception text, the
input or paths. Logs carry only the tool name and the exception class.

Transports (SDK ``mcp`` 2.x, ``mcp.server.mcpserver.MCPServer``):

- ``stdio`` (default): a local child process, no network, no key. Nothing may write to
  stdout (it is the protocol channel), so logs go to stderr and ``logs/``.
- ``http`` (streamable HTTP): needs ``DESKPILOT_API_KEY``; every request must carry
  ``X-API-Key: <key>`` or ``Authorization: Bearer <key>``, compared in constant time.
"""

import json
import logging
import re
from collections.abc import Awaitable
from typing import Annotated, Any, TypeVar

import anyio
import uvicorn
from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from pydantic import Field, TypeAdapter, ValidationError
from starlette.datastructures import Headers
from starlette.types import ASGIApp, Receive, Scope, Send

from src.api.app import ApiServices, _Runner, _to_response, build_services
from src.api.errors import ApiError
from src.api.repository import MetricScope, RepositoryUnavailableError
from src.api.schemas import (
    TICKET_ID_PATTERN,
    AreaMetricsResponse,
    AreaName,
    BuscarSolucionResponse,
    Canal,
    Categoria,
    CrearTicketResponse,
    TicketStatusResponse,
    build_create_request,
    build_search_request,
)
from src.api.security import API_KEY_HEADER, keys_match
from src.api.ticket_service import TicketService
from src.llm import NoLLM
from src.utils.config import Settings
from src.utils.config import require_api_key as settings_api_key
from src.vectordb.chroma_store import IndexNotFoundError

logger = logging.getLogger(__name__)

T = TypeVar("T")

SERVER_NAME = "deskpilot-ai"
TOOL_NAMES = ("buscar_solucion", "consultar_estado_ticket", "metricas_area", "crear_ticket")
INSTRUCTIONS = (
    "Tools of the Banco Altiplano (fictional) L1 service desk agent; data is synthetic. "
    "Never send passwords, PINs or card numbers in any argument."
)

MSG_INDEX = "The knowledge base index is not ready."
MSG_DB = "The ticket database is unavailable."
MSG_TIMEOUT = "The request took too long."
MSG_INTERNAL = "Internal error."
MSG_TICKET_404 = "Ticket not found."
MSG_METRICS_404 = "No tickets found for that name."
MSG_EXACTLY_ONE = "Provide exactly one of area or sucursal."

_AREA = TypeAdapter(AreaName)


def _invalid(exc: ValidationError) -> ToolError:
    """Field names only: the rejected values are the caller's data and may be sensitive."""
    fields = sorted({".".join(str(p) for p in err["loc"]) for err in exc.errors()})
    return ToolError(f"Invalid arguments: {', '.join(fields)}.")


async def _guarded(tool: str, call: Awaitable[T]) -> T:
    """Await ``call``; turn every failure into a ``ToolError`` with a fixed message."""
    try:
        return await call
    except IndexNotFoundError:
        logger.error("Tool %s without an index; run: python main.py index", tool)
        raise ToolError(MSG_INDEX) from None
    except RepositoryUnavailableError:
        raise ToolError(MSG_DB) from None
    except ApiError as exc:  # the runner raises 504 on timeout
        raise ToolError(MSG_TIMEOUT if exc.status_code == 504 else MSG_INTERNAL) from None
    except Exception as exc:
        logger.error("Tool %s failed", tool, extra={"error": type(exc).__name__})
        raise ToolError(MSG_INTERNAL) from None


def build_mcp_server(settings: Settings, services: ApiServices | None = None) -> MCPServer[Any]:
    """MCP server for ``settings``; ``services`` defaults to the real ones (tests inject fakes)."""
    resolved = services if services is not None else build_services(settings)
    tickets = resolved.tickets or TicketService(resolved.repository, NoLLM(), settings)
    runner = _Runner(settings.api.request_timeout_s)
    search_model = build_search_request(settings.api.max_query_chars)
    create_model = build_create_request(settings.api.max_description_chars)
    # Limits go in the schema only (json_schema_extra): the SDK must not validate and echo the
    # value in its error; the REST request models above validate, with fixed error messages.
    query_hint = {"maxLength": settings.api.max_query_chars}
    description_hint = {"maxLength": settings.api.max_description_chars}
    id_hint = {"pattern": TICKET_ID_PATTERN}

    server: MCPServer[Any] = MCPServer(
        SERVER_NAME, instructions=INSTRUCTIONS, version="0.1.0", log_level=settings.app.log_level
    )

    @server.tool(name="buscar_solucion", structured_output=True)
    async def buscar_solucion(
        query: Annotated[
            str,
            Field(
                description="Problem described by the employee, in Spanish or English.",
                json_schema_extra=query_hint,
            ),
        ],
        categoria: Annotated[
            Categoria | None, Field(description="Optional knowledge base category filter.")
        ] = None,
    ) -> BuscarSolucionResponse:
        """Search the knowledge base and answer with citations, or say it does not know."""
        try:
            request = search_model(query=query, categoria=categoria)
        except ValidationError as exc:
            raise _invalid(exc) from None
        answer = await _guarded(
            "buscar_solucion", runner.run(resolved.answers.answer, request.query, request.categoria)
        )
        return _to_response(answer)

    @server.tool(name="consultar_estado_ticket", structured_output=True)
    async def consultar_estado_ticket(
        ticket_id: Annotated[
            str, Field(description="Ticket id, e.g. TCK-000001.", json_schema_extra=id_hint)
        ],
    ) -> TicketStatusResponse:
        """Status, priority and SLA of a ticket."""
        if not re.fullmatch(TICKET_ID_PATTERN, ticket_id):
            raise ToolError("Invalid arguments: ticket_id.")
        status = await _guarded(
            "consultar_estado_ticket", runner.run(resolved.repository.get_ticket_status, ticket_id)
        )
        if status is None:
            raise ToolError(MSG_TICKET_404)
        return status

    @server.tool(name="metricas_area", structured_output=True)
    async def metricas_area(
        area: Annotated[str | None, Field(description="Area name.")] = None,
        sucursal: Annotated[str | None, Field(description="Branch name.")] = None,
    ) -> AreaMetricsResponse:
        """Ticket metrics (volume, SLA, resolution time, top categories) of an area or branch."""
        if (area is None) == (sucursal is None):
            raise ToolError(MSG_EXACTLY_ONE)
        scope: MetricScope = "area" if area is not None else "sucursal"
        try:
            name = _AREA.validate_python(area if area is not None else sucursal)
        except ValidationError:
            raise ToolError(f"Invalid arguments: {scope}.") from None
        metrics = await _guarded(
            "metricas_area", runner.run(resolved.repository.area_metrics, scope, name)
        )
        if metrics is None:
            raise ToolError(MSG_METRICS_404)
        return metrics

    @server.tool(name="crear_ticket", structured_output=True)
    async def crear_ticket(
        descripcion: Annotated[
            str,
            Field(
                description="Problem described by the employee. Never include passwords or PINs.",
                json_schema_extra=description_hint,
            ),
        ],
        sucursal: Annotated[str, Field(description="Branch of the employee.")],
        area: Annotated[str, Field(description="Area of the employee.")],
        canal: Annotated[Canal, Field(description="Channel the request came from.")] = "Teams",
    ) -> CrearTicketResponse:
        """Create a ticket, classified by category and priority (writes data)."""
        try:
            request = create_model(
                descripcion=descripcion, sucursal=sucursal, area=area, canal=canal
            )
        except ValidationError as exc:
            raise _invalid(exc) from None
        return await _guarded("crear_ticket", runner.run(tickets.create, request))

    return server


class ApiKeyMiddleware:
    """ASGI guard of the HTTP transport: ``X-API-Key`` or ``Authorization: Bearer`` (RNF-02)."""

    def __init__(self, app: ASGIApp, api_key: str) -> None:
        self._app = app
        self._key = api_key

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":  # lifespan
            await self._app(scope, receive, send)
            return
        headers = Headers(scope=scope)
        provided = headers.get(API_KEY_HEADER)
        if provided is None:
            scheme, _, token = headers.get("authorization", "").partition(" ")
            provided = token.strip() if scheme.lower() == "bearer" else None
        if keys_match(provided, self._key):
            await self._app(scope, receive, send)
            return
        logger.warning("MCP request rejected: missing or invalid API key")
        body = json.dumps({"code": "unauthorized", "message": "Missing or invalid API key."})
        await send(
            {
                "type": "http.response.start",
                "status": 401,
                "headers": [
                    (b"content-type", b"application/json"),
                    (b"www-authenticate", f"Bearer, {API_KEY_HEADER}".encode()),
                ],
            }
        )
        await send({"type": "http.response.body", "body": body.encode()})


def build_http_app(server: MCPServer[Any], settings: Settings, host: str, path: str) -> ASGIApp:
    """Streamable HTTP ASGI app of ``server`` behind the API key (fails fast without a key)."""
    api_key = settings_api_key(settings).get_secret_value()
    app = server.streamable_http_app(
        streamable_http_path=path,
        host=host,
        max_request_body_size=settings.api.max_body_bytes,
    )
    return ApiKeyMiddleware(app, api_key)


def run_stdio(server: MCPServer[Any]) -> None:
    """Serve over stdio until the client closes the pipe."""
    server.run("stdio")


def run_http(server: MCPServer[Any], settings: Settings, host: str, port: int, path: str) -> None:
    """Serve over streamable HTTP with uvicorn (no access log: it would carry the query string)."""
    app = build_http_app(server, settings, host, path)
    config = uvicorn.Config(
        app, host=host, port=port, log_config=None, access_log=False, server_header=False
    )
    anyio.run(uvicorn.Server(config).serve)
