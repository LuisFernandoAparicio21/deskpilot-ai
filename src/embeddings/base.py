"""The ``Embedder`` interface shared by every embedding provider (S17, RNF-08)."""

from __future__ import annotations

import math
from collections.abc import Iterable
from typing import Protocol, runtime_checkable


@runtime_checkable
class Embedder(Protocol):
    """Turns text into fixed-size vectors; documents and queries may be embedded differently."""

    @property
    def dimension(self) -> int:
        """Length of every vector this embedder returns."""
        ...

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """One vector per text, in the same order."""
        ...

    def embed_query(self, text: str) -> list[float]:
        """Vector of a search query."""
        ...


def l2_normalize(values: Iterable[float]) -> list[float]:
    """Unit-length copy of ``values`` as Python floats; the zero vector stays zero."""
    vector = [float(x) for x in values]
    norm = math.sqrt(sum(x * x for x in vector))
    return [x / norm for x in vector] if norm else vector
