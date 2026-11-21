"""``VectorStore`` backed by a persistent Chroma collection with cosine distance.

Verified with chromadb 1.5.9: ``PersistentClient(path=..., settings=...)``; the space
is declared with ``configuration={"hnsw": {"space": "cosine"}}`` (the legacy metadata
key ``hnsw:space`` also works); ``query`` returns cosine *distances* (``1 - cos``,
0..2), converted here to a 0..1 similarity. Embeddings always come from our
``Embedder`` (``embedding_function=None``), so Chroma never downloads its own model.

Concurrency: a ``PersistentClient`` is thread-safe but is not documented as safe for
several processes sharing one path, so each ``main.py index`` writes a new directory
and the API only reads (see ``src/vectordb/versions.py`` and the README).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import chromadb
from chromadb.api.collection_configuration import (
    CreateCollectionConfiguration,
    CreateHNSWConfiguration,
)
from chromadb.config import Settings as ChromaSettings
from chromadb.errors import NotFoundError

from src.chunking.section_chunker import Chunk, ChunkMetadata
from src.vectordb.base import (
    ScoredChunk,
    Where,
    check_top_k,
    check_upsert,
    distance_to_similarity,
)

# Same settings object for every client: Chroma refuses a second client on the same path
# with different settings. Telemetry off: the index stays fully local.
_SETTINGS = ChromaSettings(anonymized_telemetry=False)
_CONFIGURATION = CreateCollectionConfiguration(hnsw=CreateHNSWConfiguration(space="cosine"))


class IndexNotFoundError(RuntimeError):
    """There is no usable index yet; run ``python main.py index``."""


def chroma_where(where: Where | None) -> dict[str, Any] | None:
    """``{"a": "1", "b": "2"}`` -> ``{"$and": [{"a": "1"}, {"b": "2"}]}`` (Chroma syntax)."""
    if not where:
        return None
    clauses = [{key: value} for key, value in where.items()]
    return clauses[0] if len(clauses) == 1 else {"$and": clauses}


class ChromaVectorStore:
    """One Chroma collection in ``path``. ``create=False`` opens an existing index only."""

    def __init__(
        self,
        path: Path,
        collection: str,
        *,
        create: bool = True,
        metadata: Mapping[str, str | int] | None = None,
    ) -> None:
        self.path = path
        if not create and not path.is_dir():
            raise IndexNotFoundError(f"no vector index at {path}; run: python main.py index")
        self._client = chromadb.PersistentClient(path=str(path), settings=_SETTINGS)
        try:
            if create:
                self._collection = self._client.get_or_create_collection(
                    collection,
                    configuration=_CONFIGURATION,
                    metadata=dict(metadata) if metadata else None,
                    embedding_function=None,
                )
            else:
                self._collection = self._client.get_collection(collection)
        except NotFoundError as exc:
            self.close()
            raise IndexNotFoundError(
                f"collection {collection!r} not found in {path}; run: python main.py index"
            ) from exc

    @property
    def space(self) -> str:
        hnsw = self._collection.configuration_json.get("hnsw") or {}
        return str(hnsw.get("space", ""))

    @property
    def metadata(self) -> dict[str, Any]:
        return dict(self._collection.metadata or {})

    def upsert(self, chunks: Sequence[Chunk], embeddings: Sequence[Sequence[float]]) -> None:
        check_upsert(chunks, embeddings)
        if not chunks:
            return
        vectors: list[Sequence[float]] = [[float(x) for x in vector] for vector in embeddings]
        self._collection.upsert(
            ids=[c.chunk_id for c in chunks],
            embeddings=vectors,
            documents=[c.text for c in chunks],
            metadatas=[c.metadata.model_dump() for c in chunks],
        )

    def query(
        self, embedding: Sequence[float], top_k: int, where: Where | None = None
    ) -> list[ScoredChunk]:
        check_top_k(top_k)
        vectors: list[Sequence[float]] = [[float(x) for x in embedding]]
        result = self._collection.query(
            query_embeddings=vectors,
            n_results=top_k,
            where=chroma_where(where),
            include=["documents", "metadatas", "distances"],
        )
        ids = result["ids"][0]
        documents = (result["documents"] or [[]])[0]
        metadatas = (result["metadatas"] or [[]])[0]
        distances = (result["distances"] or [[]])[0]
        return [
            ScoredChunk(
                chunk=Chunk(
                    chunk_id=chunk_id,
                    text=document or "",
                    metadata=ChunkMetadata.model_validate(dict(meta or {})),
                ),
                similarity=distance_to_similarity(float(distance)),
            )
            for chunk_id, document, meta, distance in zip(
                ids, documents, metadatas, distances, strict=True
            )
        ]

    def count(self) -> int:
        return self._collection.count()

    def close(self) -> None:
        """Release the SQLite/HNSW files (on Windows an open index cannot be moved)."""
        close = getattr(self._client, "close", None)
        if callable(close):
            close()
