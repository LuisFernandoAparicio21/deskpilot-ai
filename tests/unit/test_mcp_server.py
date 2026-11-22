"""Unit tests of the MCP server (T18, S10): tools, schemas, validation, errors, redaction."""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any, TypeVar

import anyio
import pytest
from mcp import Client
from mcp.types import CallToolResult

from src.api.mcp_server import (
    INSTRUCTIONS,
    MSG_DB,
    MSG_EXACTLY_ONE,
    MSG_INDEX,
    MSG_INTERNAL,
    MSG_METRICS_404,
    MSG_TICKET_404,
    MSG_TIMEOUT,
    TOOL_NAMES,
    build_mcp_server,
)
from src.api.repository import RepositoryUnavailableError
from src.vectordb.chroma_store import IndexNotFoundError
from tests.unit.conftest import Env, settings_with_key

T = TypeVar("T")
ECHO = "zzECHOMARKER9981zz"
GOOD_CREATE: dict[str, Any] = {
    "descripcion": "La VPN es intermitente desde ayer",
    "sucursal": "Centro",
    "area": "Caja",
}


def run_with_client(env: Env, body: Callable[[Client], Awaitable[T]]) -> T:
    """Run ``body`` against an in-process MCP client of a server over the fakes of ``env``."""

    async def go() -> T:
        server = build_mcp_server(env.settings, env.services())
        async with Client(server) as client:
            return await body(client)

    return anyio.run(go)


def call(env: Env, tool: str, args: dict[str, Any]) -> CallToolResult:
    async def body(client: Client) -> CallToolResult:
        return await client.call_tool(tool, args)

    return run_with_client(env, body)


def error_text(result: CallToolResult) -> str:
    assert result.is_error
    assert result.structured_content is None
    return "".join(getattr(block, "text", "") for block in result.content)


def log_dump(caplog: pytest.LogCaptureFixture) -> str:
    return "\n".join(f"{r.getMessage()} {r.__dict__} {r.exc_info}" for r in caplog.records)


# --- list_tools ------------------------------------------------------------------------------


def test_lists_exactly_the_four_tools_with_descriptions(env: Env) -> None:
    async def body(client: Client) -> Any:
        return (await client.list_tools()).tools

    tools = run_with_client(env, body)
    assert sorted(t.name for t in tools) == sorted(TOOL_NAMES)
    assert len(tools) == 4
    for tool in tools:
        assert tool.description
        assert len(tool.description) > 15
        assert tool.input_schema["type"] == "object"
        assert tool.output_schema is not None


def test_input_schemas_declare_the_right_parameters(env: Env) -> None:
    async def body(client: Client) -> Any:
        return {t.name: t.input_schema for t in (await client.list_tools()).tools}

    schemas = run_with_client(env, body)
    api = env.settings.api
    search = schemas["buscar_solucion"]
    assert set(search["properties"]) == {"query", "categoria"}
    assert search["required"] == ["query"]
    assert search["properties"]["query"]["type"] == "string"
    assert search["properties"]["query"]["maxLength"] == api.max_query_chars

    status = schemas["consultar_estado_ticket"]
    assert set(status["properties"]) == {"ticket_id"}
    assert status["required"] == ["ticket_id"]
    assert "pattern" in status["properties"]["ticket_id"]

    metrics = schemas["metricas_area"]
    assert set(metrics["properties"]) == {"area", "sucursal"}
    assert not metrics.get("required")

    create = schemas["crear_ticket"]
    assert set(create["properties"]) == {"descripcion", "sucursal", "area", "canal"}
    assert sorted(create["required"]) == ["area", "descripcion", "sucursal"]
    assert create["properties"]["descripcion"]["maxLength"] == api.max_description_chars
    assert create["properties"]["canal"]["enum"] == ["portal", "correo", "teléfono", "Teams"]


def test_server_instructions_forbid_secrets_in_arguments() -> None:
    assert "passwords" in INSTRUCTIONS
    assert "Banco Altiplano" in INSTRUCTIONS


# --- calling the tools with fakes ------------------------------------------------------------


def test_buscar_solucion_returns_structured_answer_with_citations(env: Env) -> None:
    result = call(env, "buscar_solucion", {"query": "no puedo entrar", "categoria": "Accesos"})
    assert not result.is_error
    data = result.structured_content
    assert data is not None
    assert data["status"] == "answered"
    assert data["language"] == "es"
    assert data["citations"][0]["article_id"] == "KB-001"
    assert env.search.calls == [("no puedo entrar", "Accesos")]


def test_consultar_estado_ticket_returns_structured_status(env: Env) -> None:
    result = call(env, "consultar_estado_ticket", {"ticket_id": "TCK-000001"})
    assert not result.is_error
    assert result.structured_content == {
        "ticket_id": "TCK-000001",
        "estado": "abierto",
        "prioridad": "P1",
        "fecha_apertura": "2025-11-01T09:00:00",
        "fecha_cierre": None,
        "sla_horas": 4,
        "fecha_limite_sla": "2025-11-01T13:00:00",
        "sla_cumplido": None,
    }
    assert env.repo.ticket_calls == ["TCK-000001"]


@pytest.mark.parametrize("arg", ["area", "sucursal"])
def test_metricas_area_returns_metrics_for_area_or_branch(env: Env, arg: str) -> None:
    result = call(env, "metricas_area", {arg: "Caja"})
    assert not result.is_error
    data = result.structured_content
    assert data is not None
    assert (data["scope"], data["name"], data["total_tickets"]) == (arg, "Caja", 10)
    assert data["sla_cumplido_pct"] == 75.0
    assert env.repo.metric_calls == [(arg, "Caja")]


def test_crear_ticket_stores_and_returns_the_ticket(env: Env) -> None:
    result = call(env, "crear_ticket", {**GOOD_CREATE, "canal": "portal"})
    assert not result.is_error
    data = result.structured_content
    assert data is not None
    assert data["ticket_id"] == "TCK-100001"
    assert (data["prioridad"], data["sla_horas"]) == ("P3", 24)
    assert data["escalado"] is False
    (stored,) = env.repo.created
    assert (stored.sucursal, stored.area, stored.canal) == ("Centro", "Caja", "portal")
    assert stored.descripcion == GOOD_CREATE["descripcion"]


def test_crear_ticket_default_channel_is_teams(env: Env) -> None:
    assert not call(env, "crear_ticket", GOOD_CREATE).is_error
    assert env.repo.created[0].canal == "Teams"


@pytest.mark.parametrize(
    "text",
    [
        "Veo cargos no reconocidos en la cuenta de un cliente",
        "Alguien más entró a mi cuenta, acceso no autorizado",
        "The cash register is frozen",
    ],
)
def test_rn03_escalation_is_p1_through_mcp(env: Env, text: str) -> None:
    result = call(env, "crear_ticket", {**GOOD_CREATE, "descripcion": text})
    data = result.structured_content
    assert data is not None
    assert data["prioridad"] == "P1"
    assert data["sla_horas"] == 4
    assert data["escalado"] is True
    assert data["motivo_escalamiento"]
    assert env.repo.created[0].prioridad == "P1"


# --- validation: fixed messages, no echo of the input ----------------------------------------


@pytest.mark.parametrize("query", ["", "   ", "\n\t"])
def test_empty_query_is_rejected_without_calling_the_service(env: Env, query: str) -> None:
    result = call(env, "buscar_solucion", {"query": query})
    assert error_text(result).endswith("Invalid arguments: query.")
    assert env.search.calls == []


def test_too_long_query_is_rejected_without_echo(env: Env) -> None:
    query = ECHO + "a" * (env.settings.api.max_query_chars + 1)
    text = error_text(call(env, "buscar_solucion", {"query": query}))
    assert text.endswith("Invalid arguments: query.")
    assert ECHO not in text
    assert env.search.calls == []


def test_query_at_the_limit_is_accepted(env: Env) -> None:
    query = "a" * env.settings.api.max_query_chars
    assert not call(env, "buscar_solucion", {"query": query}).is_error


LITERAL_ECHO_BUG = pytest.mark.xfail(
    strict=True,
    reason=(
        "BUG src/api/mcp_server.py:125 (categoria) and :186 (canal): Literal parameters are "
        "validated by the SDK, whose ToolError carries pydantic's input_value, so the rejected "
        "input is echoed (expected: fixed 'Invalid arguments: <field>.' message)."
    ),
)


def test_invalid_categoria_is_rejected_and_never_reaches_the_service(env: Env) -> None:
    assert call(env, "buscar_solucion", {"query": "hola", "categoria": ECHO}).is_error
    assert env.search.calls == []


@LITERAL_ECHO_BUG
def test_invalid_categoria_is_rejected_without_echo(env: Env) -> None:
    text = error_text(call(env, "buscar_solucion", {"query": "hola", "categoria": ECHO}))
    assert ECHO not in text


@pytest.mark.parametrize("ticket_id", ["", "bad id", "TCK/../etc", ECHO + "!!!", "T" * 33])
def test_invalid_ticket_id_is_rejected_without_echo(env: Env, ticket_id: str) -> None:
    text = error_text(call(env, "consultar_estado_ticket", {"ticket_id": ticket_id}))
    assert text.endswith("Invalid arguments: ticket_id.")
    assert ECHO not in text
    assert "etc" not in text
    assert env.repo.ticket_calls == []


@pytest.mark.parametrize(
    "args", [{}, {"area": "Caja", "sucursal": "Centro"}], ids=["neither", "both"]
)
def test_metricas_needs_exactly_one_of_area_or_sucursal(env: Env, args: dict[str, Any]) -> None:
    text = error_text(call(env, "metricas_area", args))
    assert text.endswith(MSG_EXACTLY_ONE)
    assert env.repo.metric_calls == []


@pytest.mark.parametrize("arg", ["area", "sucursal"])
def test_metricas_invalid_name_is_rejected_without_echo(env: Env, arg: str) -> None:
    text = error_text(call(env, "metricas_area", {arg: ECHO + "';DROP TABLE--"}))
    assert text.endswith(f"Invalid arguments: {arg}.")
    assert ECHO not in text
    assert env.repo.metric_calls == []


@pytest.mark.parametrize(
    ("args", "field"),
    [
        ({"descripcion": ""}, "descripcion"),
        ({"descripcion": ECHO + "a" * 2001}, "descripcion"),
        ({"sucursal": ""}, "sucursal"),
        ({"area": ""}, "area"),
        ({"sucursal": ECHO + "'; --"}, "sucursal"),
        ({"area": ECHO + "'; --"}, "area"),
    ],
)
def test_crear_ticket_validation_is_fixed_and_does_not_echo(
    env: Env, args: dict[str, Any], field: str
) -> None:
    text = error_text(call(env, "crear_ticket", {**GOOD_CREATE, **args}))
    assert ECHO not in text
    assert field in text
    assert env.repo.created == []


def test_invalid_canal_is_rejected_and_nothing_is_stored(env: Env) -> None:
    assert call(env, "crear_ticket", {**GOOD_CREATE, "canal": ECHO}).is_error
    assert env.repo.created == []


@LITERAL_ECHO_BUG
def test_invalid_canal_is_rejected_without_echo(env: Env) -> None:
    text = error_text(call(env, "crear_ticket", {**GOOD_CREATE, "canal": ECHO}))
    assert ECHO not in text


def test_error_messages_are_fixed_across_different_inputs(env: Env) -> None:
    first = error_text(call(env, "consultar_estado_ticket", {"ticket_id": "bad one"}))
    second = error_text(call(env, "consultar_estado_ticket", {"ticket_id": "other/bad"}))
    assert first == second


def test_missing_required_argument_is_a_tool_error(env: Env) -> None:
    assert call(env, "crear_ticket", {"descripcion": "algo roto"}).is_error
    assert call(env, "consultar_estado_ticket", {}).is_error
    assert call(env, "buscar_solucion", {}).is_error
    assert env.repo.created == []


@pytest.mark.xfail(
    strict=True,
    reason=(
        "BUG src/api/mcp_server.py:116-195: unknown arguments are ignored by the SDK-built "
        "argument model instead of being rejected like the REST models (extra=forbid)."
    ),
)
@pytest.mark.parametrize(
    ("tool", "args"),
    [
        ("buscar_solucion", {"query": "hola", "extra": 1}),
        ("consultar_estado_ticket", {"ticket_id": "TCK-000001", "extra": 1}),
        ("metricas_area", {"area": "Caja", "extra": 1}),
        ("crear_ticket", {**GOOD_CREATE, "extra": 1}),
    ],
)
def test_extra_arguments_are_rejected(env: Env, tool: str, args: dict[str, Any]) -> None:
    assert call(env, tool, args).is_error


def test_unknown_tool_never_succeeds(env: Env) -> None:
    async def body(client: Client) -> CallToolResult:
        return await client.call_tool("borrar_todo", {})

    try:
        result = run_with_client(env, body)
    except Exception:  # the SDK may raise a protocol error instead of a tool result
        return
    assert result.is_error


# --- not found and failure mapping -----------------------------------------------------------


def test_unknown_ticket_and_metrics_are_fixed_not_found_errors(env: Env) -> None:
    ticket = call(env, "consultar_estado_ticket", {"ticket_id": "TCK-999999"})
    assert error_text(ticket).endswith(MSG_TICKET_404)
    metrics = call(env, "metricas_area", {"area": "Inexistente"})
    assert error_text(metrics).endswith(MSG_METRICS_404)


@pytest.mark.parametrize(
    ("error", "message"),
    [
        (IndexNotFoundError("path C:/secret/index hunter2"), MSG_INDEX),
        (RepositoryUnavailableError("dsn=Server=hidden;PWD=hunter2"), MSG_DB),
        (RuntimeError("boom PWD=hunter2 C:/Users/x"), MSG_INTERNAL),
    ],
)
def test_search_failures_map_to_fixed_messages(
    env: Env, caplog: pytest.LogCaptureFixture, error: Exception, message: str
) -> None:
    env.search.error = error
    caplog.set_level(logging.DEBUG)
    text = error_text(call(env, "buscar_solucion", {"query": "hola"}))
    assert text.endswith(message)
    assert "hunter2" not in text
    assert "C:/" not in text
    assert "hunter2" not in log_dump(caplog)
    assert "C:/Users" not in log_dump(caplog)


@pytest.mark.parametrize("tool", ["consultar_estado_ticket", "metricas_area"])
@pytest.mark.parametrize(
    ("error", "message"),
    [
        (RepositoryUnavailableError("dsn=Server=hidden;PWD=hunter2"), MSG_DB),
        (RuntimeError("boom PWD=hunter2 C:/Users/x"), MSG_INTERNAL),
    ],
)
def test_repository_failures_map_to_fixed_messages(
    env: Env, caplog: pytest.LogCaptureFixture, tool: str, error: Exception, message: str
) -> None:
    env.repo.error = error
    caplog.set_level(logging.DEBUG)
    args = {"ticket_id": "TCK-000001"} if tool == "consultar_estado_ticket" else {"area": "Caja"}
    text = error_text(call(env, tool, args))
    assert text.endswith(message)
    assert "hunter2" not in text
    assert "hunter2" not in log_dump(caplog)


def test_failure_is_logged_with_tool_and_exception_class_only(
    env: Env, caplog: pytest.LogCaptureFixture
) -> None:
    env.search.error = RuntimeError("leaky detail 12345")
    caplog.set_level(logging.DEBUG)
    call(env, "buscar_solucion", {"query": "consulta privada xyz"})
    records = [r for r in caplog.records if r.name == "src.api.mcp_server"]
    assert records
    assert any("buscar_solucion" in r.getMessage() for r in records)
    assert any(getattr(r, "error", None) == "RuntimeError" for r in records)
    dump = "\n".join(f"{r.getMessage()} {r.__dict__}" for r in records)
    assert "leaky detail" not in dump
    assert "consulta privada" not in dump


def test_slow_backend_times_out_with_a_fixed_message(tmp_path: Path) -> None:
    env = Env(settings_with_key(tmp_path, request_timeout_s=0.05))
    env.search.delay_s = 0.5
    assert error_text(call(env, "buscar_solucion", {"query": "hola"})).endswith(MSG_TIMEOUT)


def test_create_failure_does_not_leak_the_description(
    env: Env, caplog: pytest.LogCaptureFixture
) -> None:
    env.repo.error = RepositoryUnavailableError(f"insert failed {ECHO}")
    caplog.set_level(logging.DEBUG)
    text = error_text(call(env, "crear_ticket", GOOD_CREATE))
    assert text.endswith(MSG_DB)
    assert ECHO not in text
    assert ECHO not in log_dump(caplog)


# --- RN-05 through MCP -----------------------------------------------------------------------

SECRETS = {
    "password": ("mi contraseña es Zx9secretoPW", "Zx9secretoPW"),
    "pin": ("mi NIP es 482193", "482193"),
    "card": ("la tarjeta 4539 1488 0343 6467 fue rechazada", "4539 1488 0343 6467"),
    "token": ("token: aB3xKq9ZpLm2Wv7Rt", "aB3xKq9ZpLm2Wv7Rt"),
}


@pytest.mark.parametrize("kind", sorted(SECRETS))
def test_rn05_secret_is_neither_stored_returned_nor_logged(
    env: Env, caplog: pytest.LogCaptureFixture, kind: str
) -> None:
    sentence, secret = SECRETS[kind]
    caplog.set_level(logging.DEBUG)
    description = f"No entra el sistema. {sentence}"
    result = call(env, "crear_ticket", {**GOOD_CREATE, "descripcion": description})
    assert not result.is_error
    (stored,) = env.repo.created
    assert secret not in stored.descripcion
    assert "No entra el sistema" in stored.descripcion
    assert secret not in repr(result)
    assert secret not in log_dump(caplog)
