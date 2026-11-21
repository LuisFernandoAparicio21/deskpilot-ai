"""Vector store operations (ChromaDB) behind a swappable interface."""

from src.vectordb.base import ScoredChunk, VectorStore, Where, distance_to_similarity
from src.vectordb.chroma_store import ChromaVectorStore, IndexNotFoundError
from src.vectordb.memory import InMemoryVectorStore

__all__ = [
    "ChromaVectorStore",
    "InMemoryVectorStore",
    "IndexNotFoundError",
    "ScoredChunk",
    "VectorStore",
    "Where",
    "distance_to_similarity",
]
