"""Text embedding providers: multilingual fastembed and a deterministic fake for tests."""

from src.embeddings.base import Embedder, l2_normalize
from src.embeddings.factory import build_embedder
from src.embeddings.fake import FakeEmbedder, normalize_tokens
from src.embeddings.fastembed_embedder import FastEmbedEmbedder

__all__ = [
    "Embedder",
    "FakeEmbedder",
    "FastEmbedEmbedder",
    "build_embedder",
    "l2_normalize",
    "normalize_tokens",
]
