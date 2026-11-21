"""Vector store operations (ChromaDB) behind a swappable interface."""

from src.vectordb.base import ScoredChunk, VectorStore, Where, distance_to_similarity
from src.vectordb.chroma_store import ChromaVectorStore, IndexNotFoundError
from src.vectordb.memory import InMemoryVectorStore
from src.vectordb.versions import (
    KEEP_VERSIONS,
    POINTER_NAME,
    CurrentStore,
    IndexPointerWatcher,
    list_versions,
    new_version_name,
    open_current_store,
    prune_versions,
    read_current,
    write_current,
)

__all__ = [
    "KEEP_VERSIONS",
    "POINTER_NAME",
    "ChromaVectorStore",
    "CurrentStore",
    "InMemoryVectorStore",
    "IndexNotFoundError",
    "IndexPointerWatcher",
    "ScoredChunk",
    "VectorStore",
    "Where",
    "distance_to_similarity",
    "list_versions",
    "new_version_name",
    "open_current_store",
    "prune_versions",
    "read_current",
    "write_current",
]
