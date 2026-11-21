"""Pick the embedder named by ``embeddings.provider`` in ``config.yaml``."""

from __future__ import annotations

from src.embeddings.base import Embedder
from src.embeddings.fake import FakeEmbedder
from src.embeddings.fastembed_embedder import FastEmbedEmbedder
from src.utils.config import EmbeddingsConfig, Settings


def build_embedder(config: Settings | EmbeddingsConfig) -> Embedder:
    """``fastembed`` -> ``FastEmbedEmbedder`` (model, cache_dir); ``fake`` -> ``FakeEmbedder``."""
    embeddings = config.embeddings if isinstance(config, Settings) else config
    if embeddings.provider == "fake":
        return FakeEmbedder()
    return FastEmbedEmbedder(embeddings.model, embeddings.cache_dir)
