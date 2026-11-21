"""The ``VectorStore`` interface and the scored result shared by every store (S17, RNF-08)."""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from typing import Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field

from src.chunking.section_chunker import Chunk

Where = Mapping[str, str]
"""Equality filter on chunk metadata, e.g. ``{"categoria": "Red"}`` (keys are ANDed)."""


class ScoredChunk(BaseModel):
    """A retrieved chunk with its similarity to the query, from 0 (unrelated) to 1."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    chunk: Chunk
    similarity: float = Field(ge=0.0, le=1.0)


@runtime_checkable
class VectorStore(Protocol):
    """Stores chunk vectors and returns the most similar chunks to a query vector."""

    def upsert(self, chunks: Sequence[Chunk], embeddings: Sequence[Sequence[float]]) -> None:
        """Insert or replace ``chunks`` (by ``chunk_id``) with their vectors."""
        ...

    def query(
        self, embedding: Sequence[float], top_k: int, where: Where | None = None
    ) -> list[ScoredChunk]:
        """Up to ``top_k`` chunks, most similar first, optionally filtered by metadata."""
        ...

    def count(self) -> int:
        """Number of stored chunks."""
        ...


def distance_to_similarity(distance: float) -> float:
    """Cosine distance (``1 - cos``, range 0..2) -> cosine similarity clamped to 0..1.

    Negative cosine (opposite direction) means "unrelated" for retrieval, so it maps
    to 0; this keeps ``retrieval.similarity_threshold`` readable as a plain cosine.
    """
    if math.isnan(distance):
        return 0.0
    return min(1.0, max(0.0, 1.0 - distance))


def check_upsert(chunks: Sequence[Chunk], embeddings: Sequence[Sequence[float]]) -> None:
    """Fail fast on a chunk/vector count mismatch or vectors of different sizes."""
    if len(chunks) != len(embeddings):
        raise ValueError(f"got {len(chunks)} chunks but {len(embeddings)} embeddings")
    if len({len(vector) for vector in embeddings}) > 1:
        raise ValueError("all embeddings must have the same dimension")


def check_top_k(top_k: int) -> None:
    if top_k < 1:
        raise ValueError(f"top_k must be at least 1, got {top_k}")
