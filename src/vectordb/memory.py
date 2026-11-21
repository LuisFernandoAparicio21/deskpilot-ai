"""In-memory ``VectorStore`` for tests: exact cosine search over a dict, no files."""

from __future__ import annotations

from collections.abc import Sequence

from src.chunking.section_chunker import Chunk
from src.embeddings.base import l2_normalize
from src.vectordb.base import (
    ScoredChunk,
    Where,
    check_top_k,
    check_upsert,
    distance_to_similarity,
)


class InMemoryVectorStore:
    """Same contract as ``ChromaVectorStore`` (cosine similarity in 0..1)."""

    def __init__(self) -> None:
        self._items: dict[str, tuple[Chunk, list[float]]] = {}

    def upsert(self, chunks: Sequence[Chunk], embeddings: Sequence[Sequence[float]]) -> None:
        check_upsert(chunks, embeddings)
        for chunk, vector in zip(chunks, embeddings, strict=True):
            self._items[chunk.chunk_id] = (chunk, l2_normalize(vector))

    def query(
        self, embedding: Sequence[float], top_k: int, where: Where | None = None
    ) -> list[ScoredChunk]:
        check_top_k(top_k)
        query = l2_normalize(embedding)
        scored: list[ScoredChunk] = []
        for chunk, vector in self._items.values():
            metadata = chunk.metadata.model_dump()
            if where and any(metadata.get(key) != value for key, value in where.items()):
                continue
            cosine = sum(a * b for a, b in zip(query, vector, strict=True))
            scored.append(ScoredChunk(chunk=chunk, similarity=distance_to_similarity(1 - cosine)))
        scored.sort(key=lambda s: (-s.similarity, s.chunk.chunk_id))
        return scored[:top_k]

    def count(self) -> int:
        return len(self._items)
