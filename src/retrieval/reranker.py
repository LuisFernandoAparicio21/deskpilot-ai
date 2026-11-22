"""Optional cross-encoder second opinion on the top-1 evidence (abstention, RF-05, RN-04).

The embedding score alone cannot separate every out-of-domain query from a legitimate one
(see ``docs/research/rejection-experiment.md``). A cross-encoder reads query and passage
together and its score is far more separable. It is used only as a veto: it never reorders
or replaces the retrieved articles, so the top-3 does not change.

``fastembed`` is imported lazily and the model is loaded by ``warm()``, which the services
call at start-up and ``main.py index`` calls once to download it: never inside a request.
Raw cross-encoder outputs are logits; they are mapped to 0-1 with a sigmoid.
"""

from __future__ import annotations

import math
import os
from pathlib import Path
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from fastembed.rerank.cross_encoder import TextCrossEncoder

    from src.utils.config import Settings


class Reranker(Protocol):
    """Scores passages against a query; higher means more relevant, in 0-1."""

    def score(self, query: str, passages: list[str]) -> list[float]: ...

    def warm(self) -> None:
        """Load (and download, if needed) the model now."""


def sigmoid(value: float) -> float:
    if value >= 0:
        return 1.0 / (1.0 + math.exp(-value))
    exp = math.exp(value)
    return exp / (1.0 + exp)


class FastEmbedReranker:
    """``Reranker`` backed by a fastembed ``TextCrossEncoder`` (ONNX, CPU, no API keys)."""

    def __init__(self, model_name: str, cache_dir: Path | None = None) -> None:
        self.model_name = model_name
        self.cache_dir = cache_dir
        self._model: TextCrossEncoder | None = None

    def _get_model(self) -> TextCrossEncoder:
        if self._model is None:
            os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")
            try:
                from fastembed.rerank.cross_encoder import TextCrossEncoder
            except ImportError as exc:
                raise RuntimeError(
                    "fastembed is not installed. Run: pip install -r requirements.txt "
                    "(or set retrieval.rerank.enabled: false in config.yaml)."
                ) from exc
            cache = str(self.cache_dir) if self.cache_dir is not None else None
            self._model = TextCrossEncoder(model_name=self.model_name, cache_dir=cache)
        return self._model

    def warm(self) -> None:
        self._get_model()

    def score(self, query: str, passages: list[str]) -> list[float]:
        if not passages:
            return []
        # One passage per forward pass on purpose: with the int8 model the score of a passage
        # depends on the other passages in the batch (padding to the longest one), e.g. 0.019
        # in a batch of 3 vs 0.048 alone for the same pair. Scoring alone makes it
        # deterministic, and it is not slower (shorter sequences, no padding).
        model = self._get_model()
        return [sigmoid(float(next(iter(model.rerank(query, [p]))))) for p in passages]


def build_reranker(settings: Settings) -> Reranker | None:
    """The reranker for ``retrieval.rerank``, or None when it is off.

    It is also off with ``embeddings.provider: fake``: the fake embedder yields meaningless
    retrievals (tests, offline CI) and the cross-encoder model is not worth downloading.
    """
    rerank = settings.retrieval.rerank
    if not rerank.enabled or settings.embeddings.provider == "fake":
        return None
    return FastEmbedReranker(rerank.model, settings.embeddings.cache_dir)
