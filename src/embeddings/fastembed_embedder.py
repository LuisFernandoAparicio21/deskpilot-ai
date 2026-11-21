"""Local multilingual embeddings with fastembed (ONNX, no API keys).

Verified with fastembed 0.9.1: ``TextEmbedding(model_name=..., cache_dir=...)`` downloads
the model on first use (``sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2``:
384 dimensions, ~250 MB on disk, truncates input at 128 tokens). ``embed`` and
``query_embed`` return generators of ``numpy.ndarray`` (float32) that are not unit
length, so this wrapper L2-normalizes them. ``fastembed`` is imported lazily: building
the embedder (or asking its dimension) never loads or downloads the model.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import TYPE_CHECKING

from src.embeddings.base import l2_normalize

if TYPE_CHECKING:
    from fastembed import TextEmbedding


def _fastembed_class() -> type[TextEmbedding]:
    # huggingface_hub warns on Windows without symlink support; the cache still works.
    os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")
    try:
        from fastembed import TextEmbedding
    except ImportError as exc:
        raise RuntimeError(
            "fastembed is not installed. Run: pip install -r requirements.txt "
            "(or set embeddings.provider: fake in config.yaml)."
        ) from exc
    return TextEmbedding


class FastEmbedEmbedder:
    """``Embedder`` backed by a fastembed ``TextEmbedding`` model, loaded on first use."""

    def __init__(self, model_name: str, cache_dir: Path | None = None) -> None:
        self.model_name = model_name
        self.cache_dir = cache_dir
        self._model: TextEmbedding | None = None

    def _get_model(self) -> TextEmbedding:
        if self._model is None:
            cache = str(self.cache_dir) if self.cache_dir is not None else None
            self._model = _fastembed_class()(model_name=self.model_name, cache_dir=cache)
        return self._model

    @property
    def dimension(self) -> int:
        return int(_fastembed_class().get_embedding_size(self.model_name))

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        return [l2_normalize(vector.tolist()) for vector in self._get_model().embed(texts)]

    def embed_query(self, text: str) -> list[float]:
        vector = next(iter(self._get_model().query_embed(text)))
        return l2_normalize(vector.tolist())
