"""Section-based chunking of knowledge-base articles (S7, RF-11).

Each section of a ``KBArticle`` (Síntoma, Causa, Pasos, Cuándo escalar and, when
present, Introducción) becomes one ``Chunk``. A section longer than ``chunk_size``
characters is split into pieces that share up to ``chunk_overlap`` characters; cuts
prefer a line break, then a space, and only cut a word when it has no whitespace.

- ``chunk_id`` is deterministic: ``<article_id>#<section slug>#<n>``, for example
  ``KB-001#pasos#0``. The slug is lowercase ASCII without accents (``cuando_escalar``).
- ``text`` starts with ``"<titulo> — <sección>"`` on its own line, so the embedding
  carries the article topic; ``chunk_size`` applies to the section text after it.
- ``metadata`` is flat and all strings (ready for the vector store): article id, title,
  category, subcategory, language, section slug, keywords joined with ", " and source.
"""

from __future__ import annotations

import re
import unicodedata
from collections import Counter
from collections.abc import Iterable

from pydantic import BaseModel, ConfigDict

from src.ingestion.documents import KBArticle
from src.utils.config import ChunkingConfig


class ChunkMetadata(BaseModel):
    """Flat metadata stored next to each chunk to filter and cite the source."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    article_id: str
    titulo: str
    categoria: str
    subcategoria: str
    idioma: str
    seccion: str
    palabras_clave: str
    source: str


class Chunk(BaseModel):
    """One retrievable piece of an article section."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    chunk_id: str
    text: str
    metadata: ChunkMetadata


def section_slug(title: str) -> str:
    """``"Cuándo escalar"`` -> ``"cuando_escalar"``: lowercase ASCII, ``_`` separators."""
    ascii_text = unicodedata.normalize("NFKD", title).encode("ascii", "ignore").decode()
    slug = re.sub(r"[^a-z0-9]+", "_", ascii_text.lower()).strip("_")
    if not slug:
        raise ValueError(f"no se puede generar un slug para la sección {title!r}")
    return slug


def _check_sizes(chunk_size: int, chunk_overlap: int) -> None:
    if chunk_size <= 0:
        raise ValueError("chunk_size debe ser mayor que 0")
    if not 0 <= chunk_overlap < chunk_size:
        raise ValueError("chunk_overlap debe estar entre 0 y chunk_size - 1")


def _break_point(text: str, start: int, end: int, min_len: int) -> int:
    """End of the piece that starts at ``start``: a line break, then a space, else ``end``."""
    if text[end] == "\n":
        return end
    window = text[start:end]
    newline = window.rfind("\n", min_len)
    if newline != -1:
        return start + newline + 1
    if text[end].isspace():
        return end
    space = window.rfind(" ", min_len)
    return start + space + 1 if space != -1 else end


def _next_start(text: str, start: int, end: int, chunk_overlap: int) -> int:
    """Start of the next piece: ``chunk_overlap`` characters back, moved to a word start."""
    nxt = end
    if chunk_overlap:
        nxt = max(end - chunk_overlap, start + 1)
        if not text[nxt - 1].isspace():
            match = re.search(r"\s", text[nxt:end])
            if match is not None:
                nxt += match.start()
    while nxt < len(text) and text[nxt].isspace():
        nxt += 1
    return nxt


def split_text(text: str, *, chunk_size: int, chunk_overlap: int) -> list[str]:
    """Split ``text`` into pieces of at most ``chunk_size`` characters with overlap."""
    _check_sizes(chunk_size, chunk_overlap)
    text = text.strip()
    if len(text) <= chunk_size:
        return [text] if text else []
    min_len = max(chunk_overlap + 1, chunk_size // 2)
    pieces: list[str] = []
    start = 0
    while True:
        end = min(start + chunk_size, len(text))
        if end < len(text):
            end = _break_point(text, start, end, min_len)
        pieces.append(text[start:end].strip())
        if end >= len(text):
            return pieces
        start = _next_start(text, start, end, chunk_overlap)


def chunk_article(article: KBArticle, *, chunk_size: int, chunk_overlap: int) -> list[Chunk]:
    """One chunk per section of ``article`` (more when a section exceeds ``chunk_size``)."""
    _check_sizes(chunk_size, chunk_overlap)
    keywords = ", ".join(article.palabras_clave)
    chunks: list[Chunk] = []
    seen: set[str] = set()
    for title, body in article.secciones.items():
        slug = section_slug(title)
        if slug in seen:
            raise ValueError(f"sección repetida en {article.id}: {article.id}#{slug}")
        seen.add(slug)
        metadata = ChunkMetadata(
            article_id=article.id,
            titulo=article.titulo,
            categoria=article.categoria,
            subcategoria=article.subcategoria,
            idioma=article.idioma,
            seccion=slug,
            palabras_clave=keywords,
            source=article.source_path,
        )
        pieces = split_text(body, chunk_size=chunk_size, chunk_overlap=chunk_overlap)
        chunks.extend(
            Chunk(
                chunk_id=f"{article.id}#{slug}#{index}",
                text=f"{article.titulo} — {title}\n{piece}",
                metadata=metadata,
            )
            for index, piece in enumerate(pieces)
        )
    return chunks


def chunk_articles(articles: Iterable[KBArticle], config: ChunkingConfig) -> list[Chunk]:
    """Chunk every article with the ``chunking`` section of ``config.yaml``."""
    chunks: list[Chunk] = []
    for article in articles:
        chunks.extend(
            chunk_article(article, chunk_size=config.chunk_size, chunk_overlap=config.chunk_overlap)
        )
    counts = Counter(chunk.chunk_id for chunk in chunks)
    duplicates = sorted(chunk_id for chunk_id, n in counts.items() if n > 1)
    if duplicates:
        raise ValueError(f"chunk_id duplicado: {', '.join(duplicates)}")
    return chunks
