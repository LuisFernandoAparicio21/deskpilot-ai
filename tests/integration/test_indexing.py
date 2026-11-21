"""Integration: index the real knowledge base with the fake embedder (S7, RF-11, RF-15, HU-08)."""

from __future__ import annotations

import shutil
from collections.abc import Iterator
from pathlib import Path

import pytest

from src.chunking.section_chunker import chunk_articles
from src.embeddings import FakeEmbedder
from src.ingestion.documents import DocumentError, load_knowledge_base
from src.utils.config import PROJECT_ROOT, Settings, load_settings
from src.utils.logging import shutdown_logging
from src.vectordb import CurrentStore, list_versions, open_current_store, read_current
from src.vectordb.indexer import IndexBuildError, build_index

REAL_KB = PROJECT_ROOT / "data" / "knowledge_base"
EMBEDDER = FakeEmbedder()

NEW_ARTICLE = """---
id: KB-016
titulo: Reloj checador biométrico que no reconoce la huella
categoria: Hardware
subcategoria: Reloj checador
idioma: es
fecha_actualizacion: 2026-11-21
palabras_clave:
  - reloj checador
  - huella
---

# Reloj checador biométrico que no reconoce la huella

## Síntoma

El reloj checador biométrico de la sucursal no reconoce la huella del colaborador.

## Causa

El lector biométrico tiene el cristal sucio o la huella registrada está desgastada.

## Pasos

1. Limpia el cristal del lector biométrico con un paño seco.
2. Coloca el dedo centrado y sin presionar de más.

## Cuándo escalar

Si el reloj checador sigue sin reconocer ninguna huella, escala a Soporte en sitio.
"""


def _settings(tmp_path: Path, knowledge_base: Path) -> Settings:
    settings = load_settings(env_file=tmp_path / "missing.env")
    paths = settings.paths.model_copy(
        update={
            "knowledge_base": knowledge_base,
            "vectordb": tmp_path / "vectordb",
            "logs": tmp_path / "logs",
        }
    )
    embeddings = settings.embeddings.model_copy(update={"provider": "fake"})
    return settings.model_copy(update={"paths": paths, "embeddings": embeddings})


@pytest.fixture
def kb_copy(tmp_path: Path) -> Iterator[Path]:
    """Writable copy of the real knowledge base."""
    target = tmp_path / "knowledge_base"
    shutil.copytree(REAL_KB, target)
    yield target
    shutdown_logging()


def test_index_real_knowledge_base_and_query_it(tmp_path: Path) -> None:
    settings = _settings(tmp_path, REAL_KB)
    expected = chunk_articles(load_knowledge_base(REAL_KB), settings.chunking)

    result = build_index(settings, EMBEDDER)

    assert result.n_articles == 15
    assert result.n_chunks == len(expected)
    assert result.dimension == EMBEDDER.dimension
    assert read_current(settings.paths.vectordb) == result.version
    store = open_current_store(settings)
    try:
        assert store.count() == len(expected)
        assert store.metadata["embedding_provider"] == "fake"
        query = EMBEDDER.embed_query("La cuenta está bloqueada por intentos fallidos")
        top = store.query(query, top_k=3)
        assert top[0].chunk.metadata.article_id == "KB-002"
        assert top[0].chunk.metadata.titulo.startswith("Desbloquear un usuario")
        by_category = store.query(query, top_k=50, where={"categoria": "Conectividad"})
        assert by_category
        assert {r.chunk.metadata.categoria for r in by_category} == {"Conectividad"}
    finally:
        store.close()


def test_new_article_is_found_after_reindexing_hu08(kb_copy: Path, tmp_path: Path) -> None:
    settings = _settings(tmp_path, kb_copy)
    first = build_index(settings, EMBEDDER)
    current = CurrentStore.from_settings(settings)
    query = EMBEDDER.embed_query("el reloj checador no reconoce mi huella")
    try:
        before = current.get().query(query, top_k=1)
        assert before[0].chunk.metadata.article_id != "KB-016"

        (kb_copy / "KB-016-reloj-checador.md").write_text(NEW_ARTICLE, encoding="utf-8")
        second = build_index(settings, EMBEDDER)

        assert second.n_articles == first.n_articles + 1
        assert second.version != first.version
        after = current.get().query(query, top_k=1)  # reopened without restarting
        assert current.version == second.version
        assert after[0].chunk.metadata.article_id == "KB-016"
        assert after[0].chunk.metadata.titulo.startswith("Reloj checador")
    finally:
        current.close()


def test_reindexing_keeps_only_the_two_newest_versions(kb_copy: Path, tmp_path: Path) -> None:
    settings = _settings(tmp_path, kb_copy)
    results = [build_index(settings, EMBEDDER) for _ in range(3)]
    assert list_versions(settings.paths.vectordb) == [r.version for r in results[1:]]
    assert results[2].removed == [results[0].version]


def test_failed_build_leaves_the_current_index_untouched(kb_copy: Path, tmp_path: Path) -> None:
    settings = _settings(tmp_path, kb_copy)
    good = build_index(settings, EMBEDDER)
    for path in kb_copy.iterdir():
        path.unlink()
    with pytest.raises(IndexBuildError, match="no chunks"):
        build_index(settings, EMBEDDER)
    assert read_current(settings.paths.vectordb) == good.version
    assert list_versions(settings.paths.vectordb) == [good.version]


def test_count_mismatch_discards_the_new_version(
    kb_copy: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    settings = _settings(tmp_path, kb_copy)
    monkeypatch.setattr("src.vectordb.indexer.ChromaVectorStore.count", lambda self: 0)
    with pytest.raises(IndexBuildError, match="expected"):
        build_index(settings, EMBEDDER)
    assert read_current(settings.paths.vectordb) is None
    assert list_versions(settings.paths.vectordb) == []


def test_missing_knowledge_base_raises_document_error(tmp_path: Path) -> None:
    with pytest.raises(DocumentError):
        build_index(_settings(tmp_path, tmp_path / "nope"), EMBEDDER)
