"""Similarity search over the knowledge base, aggregated by article (S7, RF-12, RF-13).

``Retriever.search`` embeds the query, asks the vector store for the most similar
chunks and groups them by article: the score of an article is the maximum similarity
of its chunks. Articles come back best first; ``has_evidence`` is True only when the
best article reaches ``retrieval.similarity_threshold`` (RN-04: steps only come from an
article above the threshold). An optional ``categoria`` filters by metadata (RF-12).
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

from pydantic import BaseModel, ConfigDict, Field

from src.embeddings import Embedder
from src.vectordb import ScoredChunk, VectorStore

if TYPE_CHECKING:
    from src.utils.config import Settings

# Each article has 4-5 sections, so the store is asked for several chunks per article
# that may end up in the result; ``top_k`` then caps the number of articles.
CHUNKS_PER_ARTICLE = 4
# Upper bound of pieces per section when a section is reassembled (KB sections fit in 1).
MAX_SECTION_PIECES = 20
# Shorter common edges are treated as chance, not as chunk overlap.
MIN_OVERLAP_CHARS = 5

StoreSource = VectorStore | Callable[[], VectorStore]
"""A store, or a callable that returns the current one (e.g. ``CurrentStore.get``)."""


class ArticleHit(BaseModel):
    """One article with the chunks that matched the query, best chunk first."""

    model_config = ConfigDict(frozen=True)

    article_id: str
    titulo: str
    categoria: str
    score: float = Field(ge=0.0, le=1.0)
    chunks: list[ScoredChunk]

    @property
    def best_section(self) -> str:
        return self.chunks[0].chunk.metadata.seccion


class RetrievalResult(BaseModel):
    """Articles sorted by score plus the evidence decision for the threshold in use."""

    model_config = ConfigDict(frozen=True)

    articles: list[ArticleHit]
    threshold: float
    query_vector: list[float] = Field(default_factory=list, exclude=True, repr=False)

    @property
    def top(self) -> ArticleHit | None:
        return self.articles[0] if self.articles else None

    @property
    def evidence(self) -> list[ArticleHit]:
        """Articles at or above the threshold: the only ones an answer may use."""
        return [article for article in self.articles if article.score >= self.threshold]

    @property
    def has_evidence(self) -> bool:
        return bool(self.evidence)


def chunk_body(text: str) -> str:
    """Drop the ``"<titulo> — <sección>"`` line that the chunker puts first."""
    _, newline, body = text.partition("\n")
    return body.strip() if newline else text.strip()


def merge_pieces(pieces: list[str]) -> str:
    """Join consecutive pieces of one section, removing the overlap the chunker added."""
    merged = ""
    for piece in pieces:
        if not merged:
            merged = piece
            continue
        overlap = next(
            (
                n
                for n in range(min(len(merged), len(piece)), MIN_OVERLAP_CHARS - 1, -1)
                if merged.endswith(piece[:n])
            ),
            0,
        )
        merged = merged + piece[overlap:] if overlap else f"{merged}\n{piece}"
    return merged


def _piece_index(scored: ScoredChunk) -> int:
    return int(scored.chunk.chunk_id.rsplit("#", 1)[-1])


class Retriever:
    """Embeds a query, searches the store and aggregates chunks by article."""

    def __init__(
        self, embedder: Embedder, store: StoreSource, *, top_k: int, threshold: float
    ) -> None:
        if top_k < 1:
            raise ValueError(f"top_k must be at least 1, got {top_k}")
        if not 0.0 <= threshold <= 1.0:
            raise ValueError(f"threshold must be between 0 and 1, got {threshold}")
        self._embedder = embedder
        self._store = store
        self.top_k = top_k
        self.threshold = threshold

    @classmethod
    def from_settings(cls, settings: Settings, embedder: Embedder, store: StoreSource) -> Retriever:
        return cls(
            embedder,
            store,
            top_k=settings.retrieval.top_k,
            threshold=settings.retrieval.similarity_threshold,
        )

    def _current_store(self) -> VectorStore:
        if isinstance(self._store, VectorStore):
            return self._store
        return self._store()

    def search(self, query: str, categoria: str | None = None) -> RetrievalResult:
        """Up to ``top_k`` articles for ``query``, best first, optionally by category."""
        vector = self._embedder.embed_query(query)
        where = {"categoria": categoria} if categoria else None
        chunks = self._current_store().query(vector, self.top_k * CHUNKS_PER_ARTICLE, where=where)
        grouped: dict[str, list[ScoredChunk]] = {}
        for scored in sorted(chunks, key=lambda s: (-s.similarity, s.chunk.chunk_id)):
            grouped.setdefault(scored.chunk.metadata.article_id, []).append(scored)
        articles = [
            ArticleHit(
                article_id=article_id,
                titulo=items[0].chunk.metadata.titulo,
                categoria=items[0].chunk.metadata.categoria,
                score=items[0].similarity,
                chunks=items,
            )
            for article_id, items in grouped.items()
        ]
        articles.sort(key=lambda a: (-a.score, a.article_id))
        return RetrievalResult(
            articles=articles[: self.top_k], threshold=self.threshold, query_vector=vector
        )

    def section_text(self, article_id: str, seccion: str, query_vector: list[float]) -> str | None:
        """Full text of one section of an article, reassembled from the store, or None."""
        pieces = self._current_store().query(
            query_vector,
            MAX_SECTION_PIECES,
            where={"article_id": article_id, "seccion": seccion},
        )
        if not pieces:
            return None
        ordered = sorted(pieces, key=_piece_index)
        return merge_pieces([chunk_body(p.chunk.text) for p in ordered])
