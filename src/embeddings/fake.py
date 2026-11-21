"""Deterministic embedder for tests and CI: no model, no download, no network.

Each normalized token (lowercase, without accents, at least 3 characters) adds 1 to
the bucket chosen by a stable hash (BLAKE2b, not Python's salted ``hash``). Texts that
share words therefore get similar vectors, which keeps retrieval tests meaningful.
"""

from __future__ import annotations

import hashlib
import re
import unicodedata

from src.embeddings.base import l2_normalize

DEFAULT_FAKE_DIMENSION = 256
MIN_TOKEN_LENGTH = 3  # drops "de", "mi", "el", "my"... which would add noise

_TOKEN = re.compile(r"[a-z0-9]+")


def normalize_tokens(text: str) -> list[str]:
    """``"Se BLOQUEÓ mi usuario"`` -> ``["bloqueo", "usuario"]``."""
    ascii_text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    return [t for t in _TOKEN.findall(ascii_text.lower()) if len(t) >= MIN_TOKEN_LENGTH]


class FakeEmbedder:
    """Bag-of-words hashing embedder that returns unit vectors."""

    def __init__(self, dimension: int = DEFAULT_FAKE_DIMENSION) -> None:
        if dimension <= 0:
            raise ValueError(f"dimension must be positive, got {dimension}")
        self._dimension = dimension

    @property
    def dimension(self) -> int:
        return self._dimension

    def _bucket(self, token: str) -> int:
        digest = hashlib.blake2b(token.encode("utf-8"), digest_size=8).digest()
        return int.from_bytes(digest, "big") % self._dimension

    def _embed(self, text: str) -> list[float]:
        vector = [0.0] * self._dimension
        for token in normalize_tokens(text):
            vector[self._bucket(token)] += 1.0
        return l2_normalize(vector)

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self._embed(text) for text in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._embed(text)
