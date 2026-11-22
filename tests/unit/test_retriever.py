"""Unit tests for the retriever: aggregation by article, threshold and filters (RF-12, RF-13)."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

import pytest

from src.chunking.section_chunker import Chunk, ChunkMetadata
from src.retrieval import Retriever, merge_pieces
from src.utils.config import load_settings
from src.vectordb import InMemoryVectorStore, ScoredChunk, Where


class ScriptedEmbedder:
    """Returns a fixed vector per text so similarities are fully controlled."""

    def __init__(self, vectors: dict[str, list[float]]) -> None:
        self.vectors = vectors
        self.queries: list[str] = []

    @property
    def dimension(self) -> int:
        return 3

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self.vectors[text] for text in texts]

    def embed_query(self, text: str) -> list[float]:
        self.queries.append(text)
        return self.vectors[text]


def _chunk(article_id: str, seccion: str, index: int = 0, *, categoria: str = "Accesos") -> Chunk:
    return Chunk(
        chunk_id=f"{article_id}#{seccion}#{index}",
        text=f"Titulo {article_id} — {seccion}\ntexto {article_id} {seccion} {index}",
        metadata=ChunkMetadata(
            article_id=article_id,
            titulo=f"Titulo {article_id}",
            categoria=categoria,
            subcategoria="Sub",
            idioma="es",
            seccion=seccion,
            palabras_clave="a, b",
            source=f"data/knowledge_base/{article_id}.md",
        ),
    )


class RecordingStore:
    """Returns scripted results and records every query."""

    def __init__(self, results: list[ScoredChunk]) -> None:
        self.results = results
        self.calls: list[tuple[int, Where | None]] = []

    def upsert(self, chunks: Sequence[Chunk], embeddings: Sequence[Sequence[float]]) -> None:
        raise AssertionError("the retriever never writes")

    def query(
        self, embedding: Sequence[float], top_k: int, where: Where | None = None
    ) -> list[ScoredChunk]:
        self.calls.append((top_k, dict(where) if where else None))
        return self.results[:top_k]

    def count(self) -> int:
        return len(self.results)


def _scored(chunk: Chunk, similarity: float) -> ScoredChunk:
    return ScoredChunk(chunk=chunk, similarity=similarity)


QUERY_VECTOR = [1.0, 0.0, 0.0]


def _retriever(store: object, *, top_k: int = 3, threshold: float = 0.5) -> Retriever:
    embedder = ScriptedEmbedder({"consulta": QUERY_VECTOR})
    return Retriever(embedder, store, top_k=top_k, threshold=threshold)  # type: ignore[arg-type]


def test_groups_chunks_by_article_with_max_score_and_sorts() -> None:
    store = RecordingStore(
        [
            _scored(_chunk("KB-002", "sintoma"), 0.81),
            _scored(_chunk("KB-001", "pasos"), 0.70),
            _scored(_chunk("KB-002", "pasos"), 0.65),
            _scored(_chunk("KB-003", "causa"), 0.40),
        ]
    )
    result = _retriever(store).search("consulta")

    assert [a.article_id for a in result.articles] == ["KB-002", "KB-001", "KB-003"]
    top = result.articles[0]
    assert top.score == pytest.approx(0.81)
    assert top.titulo == "Titulo KB-002"
    assert top.best_section == "sintoma"
    assert [c.chunk.chunk_id for c in top.chunks] == ["KB-002#sintoma#0", "KB-002#pasos#0"]
    assert result.has_evidence
    assert result.top is top
    assert [a.article_id for a in result.evidence] == ["KB-002", "KB-001"]


def test_queries_more_chunks_than_articles_and_caps_articles_at_top_k() -> None:
    results = [_scored(_chunk(f"KB-{i:03d}", "pasos"), 0.9 - i / 100) for i in range(1, 10)]
    store = RecordingStore(results)
    result = _retriever(store, top_k=2).search("consulta")

    assert len(result.articles) == 2
    queried_top_k, where = store.calls[0]
    assert queried_top_k > 2  # several sections per article
    assert where is None


def test_no_evidence_below_threshold() -> None:
    store = RecordingStore([_scored(_chunk("KB-009", "sintoma"), 0.31)])
    result = _retriever(store, threshold=0.4).search("consulta")

    assert not result.has_evidence
    assert result.evidence == []
    assert result.top is not None and result.top.article_id == "KB-009"
    assert result.threshold == pytest.approx(0.4)


def test_score_equal_to_threshold_counts_as_evidence() -> None:
    store = RecordingStore([_scored(_chunk("KB-004", "pasos"), 0.5)])
    assert _retriever(store, threshold=0.5).search("consulta").has_evidence


def test_empty_store_has_no_evidence() -> None:
    result = _retriever(RecordingStore([])).search("consulta")
    assert result.articles == []
    assert result.top is None
    assert not result.has_evidence


def test_category_filter_is_passed_to_the_store() -> None:
    store = RecordingStore([])
    _retriever(store).search("consulta", categoria="Red")
    assert store.calls[0][1] == {"categoria": "Red"}


def test_category_filter_with_a_real_in_memory_store() -> None:
    a = _chunk("KB-004", "pasos", categoria="Red")
    b = _chunk("KB-002", "pasos", categoria="Accesos")
    store = InMemoryVectorStore()
    store.upsert([a, b], [[1.0, 0.0, 0.0], [1.0, 0.1, 0.0]])
    retriever = _retriever(store)

    assert {x.article_id for x in retriever.search("consulta").articles} == {"KB-004", "KB-002"}
    filtered = retriever.search("consulta", categoria="Red")
    assert [x.article_id for x in filtered.articles] == ["KB-004"]


def test_accepts_a_store_provider_called_per_search() -> None:
    store = RecordingStore([_scored(_chunk("KB-002", "pasos"), 0.9)])
    calls: list[int] = []

    def provider() -> RecordingStore:
        calls.append(1)
        return store

    retriever = _retriever(provider)
    retriever.search("consulta")
    retriever.search("consulta")
    assert len(calls) == 2


def test_section_text_reassembles_pieces_in_order_without_header() -> None:
    first = _chunk("KB-002", "pasos", 0)
    second = _chunk("KB-002", "pasos", 1)
    first = first.model_copy(update={"text": "Titulo — Pasos\n1. Espera 15 minutos.\n2. Cierra"})
    second = second.model_copy(update={"text": "Titulo — Pasos\n2. Cierra sesión.\n3. Entra."})
    store = RecordingStore([_scored(second, 0.4), _scored(first, 0.3)])
    retriever = _retriever(store)

    text = retriever.section_text("KB-002", "pasos", QUERY_VECTOR)

    assert text == "1. Espera 15 minutos.\n2. Cierra sesión.\n3. Entra."
    top_k, where = store.calls[0]
    assert where == {"article_id": "KB-002", "seccion": "pasos"}
    assert top_k >= 2


def test_section_text_is_none_when_missing() -> None:
    assert _retriever(RecordingStore([])).section_text("KB-099", "pasos", QUERY_VECTOR) is None


def test_merge_pieces_removes_overlap() -> None:
    assert merge_pieces(["uno dos tres", "dos tres cuatro"]) == "uno dos tres cuatro"
    assert merge_pieces(["abc", "xyz"]) == "abc\nxyz"
    assert merge_pieces([]) == ""


def test_search_keeps_the_query_vector_out_of_dumps() -> None:
    store = RecordingStore([_scored(_chunk("KB-002", "pasos"), 0.9)])
    result = _retriever(store).search("consulta")
    assert result.query_vector == QUERY_VECTOR
    assert "query_vector" not in result.model_dump()


def test_invalid_parameters_fail_fast() -> None:
    with pytest.raises(ValueError, match="top_k"):
        _retriever(RecordingStore([]), top_k=0)
    with pytest.raises(ValueError, match="threshold"):
        _retriever(RecordingStore([]), threshold=1.5)


def test_from_settings_uses_config_values(tmp_path: Path) -> None:
    settings = load_settings(env_file=tmp_path / "missing.env")
    store = RecordingStore([])
    retriever = Retriever.from_settings(settings, ScriptedEmbedder({}), store)
    assert retriever.top_k == settings.retrieval.top_k
    assert retriever.threshold == settings.retrieval.similarity_threshold
