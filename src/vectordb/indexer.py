"""Offline index build: knowledge base -> chunks -> embeddings -> new Chroma version.

``build_index`` is what ``python main.py index`` runs. It never runs inside an API
request: it writes a brand-new version directory, validates the chunk count, and only
then swaps ``CURRENT`` (see ``versions.py``). If anything fails, the half-built
directory is removed and the API keeps reading the previous version (RF-15, HU-08).
"""

from __future__ import annotations

import datetime as dt
import logging
import shutil
import time
from dataclasses import dataclass, field
from pathlib import Path

from src.chunking.section_chunker import chunk_articles
from src.embeddings import Embedder, build_embedder
from src.ingestion.documents import load_knowledge_base
from src.utils.config import Settings
from src.vectordb.chroma_store import ChromaVectorStore
from src.vectordb.versions import KEEP_VERSIONS, new_version_name, prune_versions, write_current

logger = logging.getLogger(__name__)


class IndexBuildError(RuntimeError):
    """The new index could not be built or failed validation; CURRENT was not changed."""


@dataclass(frozen=True)
class IndexResult:
    version: str
    path: Path
    n_articles: int
    n_chunks: int
    dimension: int
    elapsed_s: float
    removed: list[str] = field(default_factory=list)


def build_index(
    settings: Settings, embedder: Embedder | None = None, *, now: dt.datetime | None = None
) -> IndexResult:
    """Build a new index version from ``paths.knowledge_base`` and publish it."""
    started = time.perf_counter()
    embedder = embedder or build_embedder(settings)
    articles = load_knowledge_base(settings.paths.knowledge_base)
    chunks = chunk_articles(articles, settings.chunking)
    if not chunks:
        raise IndexBuildError(
            f"no chunks to index: {settings.paths.knowledge_base} has no articles"
        )
    vectors = embedder.embed_documents([chunk.text for chunk in chunks])

    root = settings.paths.vectordb
    root.mkdir(parents=True, exist_ok=True)
    version = new_version_name(now)
    path = root / version
    if path.exists():
        raise IndexBuildError(f"index version {version} already exists")
    metadata: dict[str, str | int] = {
        "embedding_provider": settings.embeddings.provider,
        "embedding_model": settings.embeddings.model,
        "dimension": embedder.dimension,
        "n_articles": len(articles),
    }
    store = ChromaVectorStore(path, settings.vectordb.collection, metadata=metadata)
    try:
        store.upsert(chunks, vectors)
        stored = store.count()
        if stored != len(chunks):
            raise IndexBuildError(f"expected {len(chunks)} chunks in the index, found {stored}")
    except Exception:
        store.close()
        shutil.rmtree(path, ignore_errors=True)
        raise
    store.close()

    write_current(root, version)
    removed = prune_versions(root, keep=KEEP_VERSIONS)
    result = IndexResult(
        version=version,
        path=path,
        n_articles=len(articles),
        n_chunks=len(chunks),
        dimension=embedder.dimension,
        elapsed_s=time.perf_counter() - started,
        removed=removed,
    )
    logger.info(
        "Vector index built",
        extra={
            "version": version,
            "n_articles": result.n_articles,
            "n_chunks": result.n_chunks,
            "elapsed_s": round(result.elapsed_s, 2),
        },
    )
    return result
