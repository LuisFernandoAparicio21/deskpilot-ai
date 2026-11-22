"""Shared fakes for the API unit tests: services without database, index or LLM."""

from __future__ import annotations

import time
from collections.abc import Callable, Iterator
from datetime import datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr

from src.api import ApiServices, create_app
from src.api.repository import MetricScope
from src.api.schemas import AreaMetricsResponse, TicketStatusResponse
from src.retrieval.answer_service import Answer, Citation
from src.utils.config import Secrets, Settings, load_settings

API_KEY = "test-key-0123456789-abcdef"
KEY_HEADER = {"X-API-Key": API_KEY}


class FakeSearch:
    """Records calls; ``error`` is raised, ``delay_s`` simulates a slow search."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, str | None]] = []
        self.error: Exception | None = None
        self.delay_s = 0.0

    def answer(self, query: str, categoria: str | None = None) -> Answer:
        self.calls.append((query, categoria))
        if self.delay_s:
            time.sleep(self.delay_s)
        if self.error is not None:
            raise self.error
        return Answer(
            status="answered",
            language="es",
            text="Restablece la contraseña desde el portal.",
            citations=[
                Citation(article_id="KB-001", titulo="Reseteo", seccion="pasos", similarity=0.8)
            ],
            sensitive_data_warning=False,
            mode="extractive",
        )


class FakeRepository:
    """In-memory ``TicketRepository``; ``error`` is raised by every query."""

    def __init__(self) -> None:
        self.error: Exception | None = None
        self.pings = 0
        self.ping_ok = True
        self.ticket_calls: list[str] = []
        self.metric_calls: list[tuple[MetricScope, str]] = []

    def get_ticket_status(self, ticket_id: str) -> TicketStatusResponse | None:
        self.ticket_calls.append(ticket_id)
        if self.error is not None:
            raise self.error
        if ticket_id != "TCK-000001":
            return None
        opened = datetime(2025, 11, 1, 9, 0, 0)
        return TicketStatusResponse(
            ticket_id=ticket_id,
            estado="abierto",
            prioridad="P1",
            fecha_apertura=opened,
            fecha_cierre=None,
            sla_horas=4,
            fecha_limite_sla=datetime(2025, 11, 1, 13, 0, 0),
            sla_cumplido=None,
        )

    def area_metrics(self, scope: MetricScope, name: str) -> AreaMetricsResponse | None:
        self.metric_calls.append((scope, name))
        if self.error is not None:
            raise self.error
        if name != "Caja":
            return None
        return AreaMetricsResponse(
            scope=scope,
            name=name,
            total_tickets=10,
            closed_tickets=8,
            sla_cumplido_pct=75.0,
            avg_horas_resolucion=5.5,
            top_categorias=[],
        )

    def ping(self) -> bool:
        self.pings += 1
        return self.ping_ok


class Probe:
    """Index probe: returns a version, or raises ``error``."""

    def __init__(self) -> None:
        self.error: Exception | None = None
        self.calls = 0

    def __call__(self) -> str | None:
        self.calls += 1
        if self.error is not None:
            raise self.error
        return "v-test"


class Env:
    """The pieces of one test app, so a test can tune the fakes."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.search = FakeSearch()
        self.repo = FakeRepository()
        self.probe = Probe()
        self.closed = 0

    def services(self) -> ApiServices:
        return ApiServices(
            answers=self.search,
            repository=self.repo,
            index_probe=self.probe,
            closers=[self._close],
        )

    def _close(self) -> None:
        self.closed += 1


def settings_with_key(tmp_path: Path, key: str | None = API_KEY, **api: float) -> Settings:
    settings = load_settings(env_file=tmp_path / "missing.env")
    secrets = Secrets(api_key=SecretStr(key) if key is not None else None)
    updated_api = settings.api.model_copy(update=api)
    return settings.model_copy(update={"secrets": secrets, "api": updated_api})


@pytest.fixture
def env(tmp_path: Path) -> Env:
    return Env(settings_with_key(tmp_path))


@pytest.fixture
def make_client() -> Iterator[Callable[[Env], TestClient]]:
    """Factory of TestClients; they are closed (lifespan shutdown) at the end."""
    clients: list[TestClient] = []

    def build(env: Env) -> TestClient:
        client = TestClient(create_app(env.settings, env.services()), raise_server_exceptions=False)
        client.__enter__()
        clients.append(client)
        return client

    yield build
    for client in clients:
        client.__exit__(None, None, None)


@pytest.fixture
def client(env: Env, make_client: Callable[[Env], TestClient]) -> TestClient:
    return make_client(env)
