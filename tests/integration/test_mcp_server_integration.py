"""Integration: MCP server over temporary SQLite (in process, HTTP, real stdio) (S10).

Nothing here touches ``data/deskpilot.db``, ``data/vectordb`` or ``logs/``: the stdio child is
``main.py mcp`` run through a tiny runner that swaps ``load_settings`` for settings whose
paths live under ``tmp_path`` (``main.py`` has no flag or variable to relocate the paths).
"""

from __future__ import annotations

import contextlib
import hashlib
import json
import os
import re
import shutil
import sqlite3
import subprocess
import sys
import textwrap
from collections.abc import AsyncIterator, Awaitable, Callable
from pathlib import Path
from typing import Any, TypeVar

import anyio
import httpx2
import pytest
from mcp import Client, StdioServerParameters
from mcp.client.streamable_http import streamable_http_client
from mcp.types import LATEST_PROTOCOL_VERSION, CallToolResult
from pydantic import SecretStr
from starlette.types import ASGIApp

from src.api import ApiServices
from src.api.mcp_server import TOOL_NAMES, build_http_app, build_mcp_server
from src.api.repository import build_repository
from src.api.ticket_service import TicketService
from src.ingestion.sqlite_loader import load_sqlite
from src.ingestion.ticket_generator import generate_dataset
from src.llm import LLMError
from src.utils.config import Secrets, Settings, load_settings
from tests.unit.conftest import API_KEY, FakeSearch, Probe
from tests.unit.test_classification import FakeLLM

T = TypeVar("T")
ROOT = Path(__file__).resolve().parents[2]
REAL_DB = ROOT / "data" / "deskpilot.db"
N_TICKETS = 300
GOOD: dict[str, Any] = {
    "descripcion": "La VPN es intermitente desde ayer",
    "sucursal": "Centro",
    "area": "Caja",
}
SECRET_SENTENCE = "mi contraseña es Zx9secretoPW"
SECRET = "Zx9secretoPW"

GENEROUS_TIMEOUT_S = 120.0


@pytest.fixture(scope="module")
def template_db(tmp_path_factory: pytest.TempPathFactory) -> Path:
    base = tmp_path_factory.mktemp("mcp")
    settings = load_settings(env_file=base / "missing.env")
    generate_dataset(
        settings.data.seed,
        N_TICKETS,
        base / "raw",
        base / "sample",
        settings.sla_horas.model_dump(),
    )
    db = base / "template.db"
    load_sqlite(base / "raw", db)
    return db


@pytest.fixture
def db(template_db: Path, tmp_path: Path) -> Path:
    copy = tmp_path / "deskpilot.db"
    shutil.copy(template_db, copy)
    return copy


def _settings(db: Path, key: str | None = API_KEY) -> Settings:
    settings = load_settings(env_file=db.parent / "missing.env")
    paths = settings.paths.model_copy(
        update={
            "sqlite_db": db,
            "logs": db.parent / "logs",
            "vectordb": db.parent / "vectordb",
            "raw": db.parent / "raw",
            "sample": db.parent / "sample",
        }
    )
    secrets = Secrets(api_key=SecretStr(key) if key else None)
    # Generous request timeout: these tests never exercise it; a slow CI runner must not trip it.
    api = settings.api.model_copy(update={"request_timeout_s": GENEROUS_TIMEOUT_S})
    return settings.model_copy(update={"paths": paths, "secrets": secrets, "api": api})


def _services(settings: Settings, llm: FakeLLM | None = None) -> ApiServices:
    repository = build_repository(settings)
    return ApiServices(
        answers=FakeSearch(),
        repository=repository,
        index_probe=Probe(),
        tickets=TicketService(repository, llm or FakeLLM(error=LLMError("off")), settings),
    )


def _sql(db: Path, sql: str) -> list[tuple[Any, ...]]:
    conn = sqlite3.connect(db)
    try:
        return conn.execute(sql).fetchall()
    finally:
        conn.close()


def _sha(path: Path) -> str | None:
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else None


def _run(body: Callable[[], Awaitable[T]]) -> T:
    return anyio.run(body)


def _text(result: CallToolResult) -> str:
    return "".join(getattr(block, "text", "") for block in result.content)


async def _exercise(client: Client, db: Path) -> None:
    """The same checks over every transport: list, then call the four tools."""
    tools = (await client.list_tools()).tools
    assert sorted(t.name for t in tools) == sorted(TOOL_NAMES)

    existing = _sql(
        db, "SELECT ticket_id, estado, prioridad FROM tickets ORDER BY ticket_id LIMIT 1"
    )
    ticket_id, estado, prioridad = existing[0]
    status = await client.call_tool("consultar_estado_ticket", {"ticket_id": ticket_id})
    assert not status.is_error
    assert status.structured_content is not None
    assert status.structured_content["ticket_id"] == ticket_id
    assert status.structured_content["estado"] == estado
    assert status.structured_content["prioridad"] == prioridad

    missing = await client.call_tool("consultar_estado_ticket", {"ticket_id": "TCK-999999"})
    assert missing.is_error
    assert _text(missing).endswith("Ticket not found.")

    area = _sql(db, "SELECT area, COUNT(*) FROM tickets GROUP BY area ORDER BY area LIMIT 1")[0]
    metrics = await client.call_tool("metricas_area", {"area": area[0]})
    assert not metrics.is_error
    assert metrics.structured_content is not None
    assert metrics.structured_content["total_tickets"] == area[1]

    answer = await client.call_tool("buscar_solucion", {"query": "no puedo entrar"})
    assert not answer.is_error
    assert answer.structured_content is not None
    assert answer.structured_content["citations"][0]["article_id"] == "KB-001"

    before = _sql(db, "SELECT COUNT(*) FROM tickets_nuevos")[0][0]
    created = await client.call_tool("crear_ticket", GOOD)
    assert not created.is_error
    assert created.structured_content is not None
    new_id = created.structured_content["ticket_id"]
    assert _sql(db, "SELECT COUNT(*) FROM tickets_nuevos")[0][0] == before + 1
    again = await client.call_tool("consultar_estado_ticket", {"ticket_id": new_id})
    assert again.structured_content is not None
    assert again.structured_content["estado"] == "abierto"
    assert again.structured_content["prioridad"] == created.structured_content["prioridad"]


# --- in process, real repository ---------------------------------------------------------------


def test_in_process_client_lists_and_calls_the_four_tools(db: Path) -> None:
    settings = _settings(db)

    async def body() -> None:
        async with Client(build_mcp_server(settings, _services(settings))) as client:
            await _exercise(client, db)

    _run(body)


def test_rn05_and_rn03_over_mcp_with_the_real_database(db: Path) -> None:
    settings = _settings(db)
    llm = FakeLLM(reply="not json")

    async def body() -> tuple[CallToolResult, CallToolResult]:
        async with Client(build_mcp_server(settings, _services(settings, llm))) as client:
            secret = await client.call_tool(
                "crear_ticket", {**GOOD, "descripcion": f"No entra el sistema. {SECRET_SENTENCE}"}
            )
            fraud = await client.call_tool(
                "crear_ticket",
                {**GOOD, "descripcion": "Veo cargos no reconocidos en la cuenta de un cliente"},
            )
            return secret, fraud

    secret, fraud = _run(body)
    assert not secret.is_error
    stored = _sql(db, "SELECT descripcion FROM tickets_nuevos ORDER BY rowid")
    assert SECRET not in json.dumps(stored)
    assert "No entra el sistema" in stored[0][0]
    assert SECRET not in repr(secret)
    assert SECRET not in " ".join(" ".join(p) for p in llm.prompts)

    assert fraud.structured_content is not None
    assert fraud.structured_content["prioridad"] == "P1"
    assert fraud.structured_content["escalado"] is True
    assert _sql(db, "SELECT prioridad, sla_horas FROM tickets_nuevos ORDER BY rowid")[1] == (
        "P1",
        4,
    )


def test_validation_errors_write_nothing(db: Path) -> None:
    settings = _settings(db)

    async def body() -> list[CallToolResult]:
        async with Client(build_mcp_server(settings, _services(settings))) as client:
            return [
                await client.call_tool("crear_ticket", {**GOOD, "descripcion": ""}),
                await client.call_tool("crear_ticket", {**GOOD, "area": ""}),
                await client.call_tool("metricas_area", {}),
                await client.call_tool("consultar_estado_ticket", {"ticket_id": "bad id"}),
            ]

    results = _run(body)
    assert all(r.is_error for r in results)
    assert _sql(db, "SELECT COUNT(*) FROM tickets_nuevos") == [(0,)]


# --- streamable HTTP, in process over ASGI -----------------------------------------------------


@contextlib.asynccontextmanager
async def _lifespan(app: ASGIApp) -> AsyncIterator[None]:
    """Drive the ASGI lifespan protocol (the MCP session manager starts there)."""
    to_app, from_app = anyio.create_memory_object_stream[dict[str, Any]](10)
    to_test, from_test = anyio.create_memory_object_stream[dict[str, Any]](10)

    async def run() -> None:
        await app({"type": "lifespan", "asgi": {"version": "3.0"}}, from_app.receive, to_test.send)  # type: ignore[arg-type]

    async with anyio.create_task_group() as tg:
        tg.start_soon(run)
        await to_app.send({"type": "lifespan.startup"})
        started = await from_test.receive()
        assert started["type"] == "lifespan.startup.complete", started
        try:
            yield
        finally:
            await to_app.send({"type": "lifespan.shutdown"})
            await from_test.receive()


def _initialize_body() -> dict[str, Any]:
    return {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": LATEST_PROTOCOL_VERSION,
            "capabilities": {},
            "clientInfo": {"name": "qa", "version": "0"},
        },
    }


MCP_HEADERS = {"Accept": "application/json, text/event-stream", "Content-Type": "application/json"}


def _http_app(settings: Settings) -> ASGIApp:
    server = build_mcp_server(settings, _services(settings))
    return build_http_app(server, settings, "127.0.0.1", settings.mcp.path)


def test_http_rejects_missing_and_wrong_keys_and_accepts_both_valid_forms(db: Path) -> None:
    settings = _settings(db)
    app = _http_app(settings)
    url = "http://127.0.0.1:8001" + settings.mcp.path

    async def body() -> dict[str, int]:
        codes: dict[str, int] = {}
        async with _lifespan(app):
            transport = httpx2.ASGITransport(app=app)
            async with httpx2.AsyncClient(transport=transport) as http:
                cases = {
                    "none": {},
                    "wrong": {"X-API-Key": "nope"},
                    "wrong-bearer": {"Authorization": "Bearer nope"},
                    "typo": {"X-API-Key": API_KEY + "x"},
                    "key": {"X-API-Key": API_KEY},
                    "bearer": {"Authorization": f"Bearer {API_KEY}"},
                }
                for name, headers in cases.items():
                    response = await http.post(
                        url, json=_initialize_body(), headers={**MCP_HEADERS, **headers}
                    )
                    codes[name] = response.status_code
                    if response.status_code == 401:
                        assert API_KEY not in response.text
                        assert "initialize" not in response.text
        return codes

    codes = _run(body)
    assert codes == {
        "none": 401,
        "wrong": 401,
        "wrong-bearer": 401,
        "typo": 401,
        "key": 200,
        "bearer": 200,
    }


@pytest.mark.parametrize("header", ["X-API-Key", "Authorization"])
def test_http_real_client_lists_and_calls_tools_with_the_key(db: Path, header: str) -> None:
    settings = _settings(db)
    app = _http_app(settings)
    value = API_KEY if header == "X-API-Key" else f"Bearer {API_KEY}"

    async def body() -> None:
        async with _lifespan(app):
            http = httpx2.AsyncClient(
                transport=httpx2.ASGITransport(app=app), headers={header: value}
            )
            async with http:
                transport = streamable_http_client(
                    "http://127.0.0.1:8001" + settings.mcp.path, http_client=http
                )
                async with Client(transport) as client:
                    await _exercise(client, db)

    _run(body)


def test_http_without_key_the_real_client_cannot_connect(db: Path) -> None:
    settings = _settings(db)
    app = _http_app(settings)

    async def body() -> None:
        async with _lifespan(app):
            http = httpx2.AsyncClient(transport=httpx2.ASGITransport(app=app))
            async with http:
                transport = streamable_http_client(
                    "http://127.0.0.1:8001" + settings.mcp.path, http_client=http
                )
                with pytest.raises(Exception):  # noqa: B017, PT011 - exact type is SDK-defined
                    async with Client(transport) as client:
                        await client.list_tools()

    _run(body)


# --- real stdio child process: main.py mcp -----------------------------------------------------

RUNNER = textwrap.dedent(
    """
    import sys
    from pathlib import Path

    root, work = Path(sys.argv[1]), Path(sys.argv[2])
    sys.path.insert(0, str(root))
    import main
    from src.utils.config import load_settings

    settings = load_settings(env_file=work / "missing.env")
    paths = settings.paths.model_copy(update={
        "sqlite_db": work / "deskpilot.db", "logs": work / "logs",
        "vectordb": work / "vectordb", "raw": work / "raw", "sample": work / "sample",
    })
    api = settings.api.model_copy(update={"request_timeout_s": 120})
    patched = settings.model_copy(update={"paths": paths, "api": api})
    main.load_settings = lambda: patched
    sys.exit(main.main(["mcp", *sys.argv[3:]]))
    """
)


def _child(db: Path, *extra: str) -> StdioServerParameters:
    runner = db.parent / "run_mcp.py"
    runner.write_text(RUNNER, encoding="utf-8")
    env = _child_env()
    return StdioServerParameters(
        command=sys.executable,
        args=[str(runner), str(ROOT), str(db.parent), *extra],
        env=env,
        cwd=str(db.parent),
    )


def _child_env() -> dict[str, str]:
    """Minimal environment: no DESKPILOT_*/API keys inherited from the developer machine."""
    keep = ("SYSTEMROOT", "PATH", "USERPROFILE", "HOME", "HOMEDRIVE", "HOMEPATH", "TEMP", "TMP")
    env = {name: os.environ[name] for name in keep if name in os.environ}
    env["PYTHONIOENCODING"] = "utf-8"
    return env


@pytest.fixture
def real_db_guard() -> Any:
    before = _sha(REAL_DB)
    yield
    assert _sha(REAL_DB) == before, "the real data/deskpilot.db was modified"


def test_stdio_child_process_serves_the_tools(db: Path, real_db_guard: Any) -> None:
    params = _child(db)

    async def body() -> None:
        async with Client(params) as client:
            tools = (await client.list_tools()).tools
            assert sorted(t.name for t in tools) == sorted(TOOL_NAMES)
            status = await client.call_tool("consultar_estado_ticket", {"ticket_id": "TCK-999999"})
            assert status.is_error
            assert _text(status).endswith("Ticket not found.")
            ticket_id = _sql(db, "SELECT ticket_id FROM tickets LIMIT 1")[0][0]
            found = await client.call_tool("consultar_estado_ticket", {"ticket_id": ticket_id})
            assert found.structured_content is not None
            assert found.structured_content["ticket_id"] == ticket_id
            area = _sql(db, "SELECT area FROM tickets LIMIT 1")[0][0]
            metrics = await client.call_tool("metricas_area", {"area": area})
            assert not metrics.is_error
            created = await client.call_tool(
                "crear_ticket", {**GOOD, "descripcion": f"Sin red. {SECRET_SENTENCE}"}
            )
            assert not created.is_error
            # No index in the temporary vectordb: a fixed message, no path or exception text.
            search = await client.call_tool("buscar_solucion", {"query": "no puedo entrar"})
            assert search.is_error
            assert _text(search).endswith("The knowledge base index is not ready.")
            assert str(db.parent) not in _text(search)

    _run(body)
    rows = _sql(db, "SELECT descripcion FROM tickets_nuevos")
    assert len(rows) == 1
    assert SECRET not in rows[0][0]
    for log in (db.parent / "logs").glob("*.log"):
        assert SECRET not in log.read_text(encoding="utf-8")


def test_stdio_stdout_carries_only_json_rpc(db: Path, real_db_guard: Any) -> None:
    """Raw pipes: every stdout line must be a JSON-RPC message; logs go to stderr only."""
    params = _child(db)
    messages = [
        _initialize_body(),
        {"jsonrpc": "2.0", "method": "notifications/initialized"},
        {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
        {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {"name": "consultar_estado_ticket", "arguments": {"ticket_id": "bad id"}},
        },
        {
            "jsonrpc": "2.0",
            "id": 4,
            "method": "tools/call",
            "params": {"name": "buscar_solucion", "arguments": {"query": "hola"}},
        },
    ]
    proc = subprocess.Popen(  # noqa: S603 - fixed argv built from sys.executable and tmp files
        [params.command, *params.args],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        cwd=params.cwd,
        env=params.env,
    )
    assert proc.stdin is not None
    assert proc.stdout is not None
    lines: list[str] = []
    try:
        for message in messages:
            proc.stdin.write(json.dumps(message) + "\n")
        proc.stdin.flush()
        while not any('"id": 4' in line or '"id":4' in line for line in lines):
            line = proc.stdout.readline()
            if not line:
                break
            lines.append(line)
    finally:
        proc.stdin.close()
        rest, stderr = proc.communicate(timeout=60)
    lines += rest.splitlines()
    assert proc.returncode == 0, stderr
    stdout = "".join(lines)
    lines = [line for line in lines if line.strip()]
    assert lines, stderr
    parsed = [json.loads(line) for line in lines]  # raises if any log line leaked to stdout
    assert all(m.get("jsonrpc") == "2.0" for m in parsed)
    by_id = {m["id"]: m for m in parsed if "id" in m}
    assert {t["name"] for t in by_id[2]["result"]["tools"]} == set(TOOL_NAMES)
    assert by_id[3]["result"]["isError"] is True
    assert by_id[4]["result"]["isError"] is True  # no index in the temporary directory
    # The logs exist (stderr and/or logs/) but never on stdout.
    assert not re.search(r"\b(INFO|WARNING|ERROR)\b", stdout.replace("isError", ""))


def test_stdio_exits_1_on_a_broken_mcp_config_without_printing_the_key(
    tmp_path: Path, real_db_guard: Any
) -> None:
    """Real child: http transport with a short key must fail fast, exit 1, key not printed."""
    short = "short-key-xyz"
    runner = tmp_path / "run_bad.py"
    runner.write_text(
        RUNNER.replace(
            'patched = settings.model_copy(update={"paths": paths})',
            "from pydantic import SecretStr\n"
            "from src.utils.config import Secrets\n"
            'patched = settings.model_copy(update={"paths": paths, '
            f'"secrets": Secrets(api_key=SecretStr("{short}"))}})',
        ),
        encoding="utf-8",
    )
    proc = subprocess.run(  # noqa: S603
        [sys.executable, str(runner), str(ROOT), str(tmp_path), "--transport", "http"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=120,
        cwd=tmp_path,
        env=_child_env(),
    )
    assert proc.returncode == 1
    assert proc.stderr.startswith("mcp: ")
    assert short not in proc.stdout + proc.stderr
    assert proc.stdout == ""
