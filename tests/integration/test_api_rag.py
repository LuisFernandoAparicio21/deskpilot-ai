"""Integration: API with the real services over a fake-embedding index (S7, S8, RF-04, RF-26)."""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr

from src.api import create_app
from src.ingestion.sqlite_loader import create_schema
from src.utils.config import PROJECT_ROOT, Secrets, Settings, load_settings
from src.utils.logging import shutdown_logging
from src.vectordb.indexer import build_index
from tests.unit.conftest import KEY_HEADER


def _settings(tmp_path: Path) -> Settings:
    settings = load_settings(env_file=tmp_path / "missing.env")
    paths = settings.paths.model_copy(
        update={
            "vectordb": tmp_path / "vectordb",
            "logs": tmp_path / "logs",
            "sqlite_db": tmp_path / "deskpilot.db",
        }
    )
    return settings.model_copy(
        update={
            "paths": paths,
            "embeddings": settings.embeddings.model_copy(update={"provider": "fake"}),
            "secrets": Secrets(api_key=SecretStr(KEY_HEADER["X-API-Key"])),
        }
    )


@pytest.fixture
def settings(tmp_path: Path) -> Iterator[Settings]:
    conn = sqlite3.connect(tmp_path / "deskpilot.db")
    create_schema(conn)
    conn.commit()
    conn.close()
    yield _settings(tmp_path)
    shutdown_logging()


def _articles_of(categoria: str) -> set[str]:
    """Article ids of a category, read from the knowledge base front matter."""
    kb = PROJECT_ROOT / "data" / "knowledge_base"
    return {
        path.name[:6]
        for path in kb.glob("KB-*.md")
        if f"\ncategoria: {categoria}\n" in path.read_text(encoding="utf-8")
    }


def test_without_an_index_search_is_503_and_health_is_degraded(settings: Settings) -> None:
    with TestClient(create_app(settings), raise_server_exceptions=False) as client:
        response = client.post(
            "/buscar_solucion", json={"query": "no puedo conectarme a la VPN"}, headers=KEY_HEADER
        )
        assert response.status_code == 503
        assert response.json()["code"] == "index_unavailable"
        assert client.get("/health").json() == {"status": "degraded"}


def test_with_an_index_search_answers_with_citations_and_health_is_ok(settings: Settings) -> None:
    result = build_index(settings)
    with TestClient(create_app(settings), raise_server_exceptions=False) as client:
        assert client.get("/health").json() == {"status": "ok"}
        assert result.version  # an index was really built for the probe to find
        response = client.post(
            "/buscar_solucion",
            json={"query": "no puedo conectarme a la VPN", "categoria": "Conectividad"},
            headers=KEY_HEADER,
        )
        body = response.json()
        assert response.status_code == 200
        assert body["status"] in {"answered", "no_evidence", "mandatory_escalation"}
        assert body["mode"] in {"extractive", "policy", "llm"}
        assert body["text"]
        if body["status"] == "answered":
            assert body["citations"]
            assert all(c["article_id"].startswith("KB-") for c in body["citations"])
        assert response.headers["X-Request-ID"]


def test_category_filter_is_applied_to_the_citations(settings: Settings) -> None:
    build_index(settings)
    with TestClient(create_app(settings), raise_server_exceptions=False) as client:
        for categoria, query in (
            ("Accesos", "Reseteo de contraseña"),
            ("Hardware", "La impresora no imprime o aparece fuera de línea"),
        ):
            body = client.post(
                "/buscar_solucion",
                json={"query": query, "categoria": categoria},
                headers=KEY_HEADER,
            ).json()
            ids = {c["article_id"] for c in body["citations"]}
            allowed = _articles_of(categoria)
            assert ids, categoria
            assert ids <= allowed, (categoria, ids)


def test_the_api_never_builds_or_changes_the_index(settings: Settings) -> None:
    with TestClient(create_app(settings), raise_server_exceptions=False) as client:
        client.post("/buscar_solucion", json={"query": "vpn"}, headers=KEY_HEADER)
        client.get("/health")
    vectordb = settings.paths.vectordb
    assert not vectordb.exists() or list(vectordb.iterdir()) == []
