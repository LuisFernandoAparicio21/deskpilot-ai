"""Unit tests for src/chunking/section_chunker.py (S7, RF-11)."""

from __future__ import annotations

import datetime as dt
from pathlib import Path

import pytest

from src.chunking.section_chunker import (
    Chunk,
    chunk_article,
    chunk_articles,
    section_slug,
    split_text,
)
from src.ingestion.documents import KBArticle, load_knowledge_base
from src.utils.config import ChunkingConfig, load_settings

KB_DIR = Path(__file__).resolve().parents[2] / "data" / "knowledge_base"
CORE_SLUGS = {"sintoma", "causa", "pasos", "cuando_escalar"}
METADATA_KEYS = {
    "article_id",
    "titulo",
    "categoria",
    "subcategoria",
    "idioma",
    "seccion",
    "palabras_clave",
    "source",
}


def _article(**sections: str) -> KBArticle:
    return KBArticle(
        id="KB-900",
        titulo="Artículo de prueba",
        categoria="Accesos",
        subcategoria="Prueba",
        idioma="es",
        fecha_actualizacion=dt.date(2026, 11, 1),
        palabras_clave=["uno", "dos"],
        secciones=sections or {"Síntoma": "Algo falla."},
        source_path="data/knowledge_base/KB-900.md",
    )


def _words(n: int) -> str:
    return " ".join(f"palabra{i:03d}" for i in range(n))


# --- Real knowledge base -------------------------------------------------------------


@pytest.fixture(scope="module")
def real_chunks() -> list[Chunk]:
    config = load_settings().chunking
    return chunk_articles(load_knowledge_base(KB_DIR), config)


def test_every_real_article_gives_at_least_four_chunks(real_chunks: list[Chunk]) -> None:
    by_article: dict[str, set[str]] = {}
    for chunk in real_chunks:
        by_article.setdefault(chunk.metadata.article_id, set()).add(chunk.metadata.seccion)
    assert sorted(by_article) == [f"KB-{n:03d}" for n in range(1, 16)]
    for article_id, slugs in by_article.items():
        assert slugs >= CORE_SLUGS, article_id
        assert sum(c.metadata.article_id == article_id for c in real_chunks) >= 4


def test_real_chunks_have_complete_metadata_and_prefix(real_chunks: list[Chunk]) -> None:
    config = load_settings().chunking
    for chunk in real_chunks:
        meta = chunk.metadata.model_dump()
        assert set(meta) == METADATA_KEYS
        assert all(isinstance(v, str) and v for v in meta.values()), chunk.chunk_id
        assert chunk.chunk_id.startswith(f"{chunk.metadata.article_id}#{chunk.metadata.seccion}#")
        assert chunk.text.startswith(f"{chunk.metadata.titulo} — ")
        body = chunk.text.split("\n", 1)[1]
        assert len(body) <= config.chunk_size
    assert len({c.chunk_id for c in real_chunks}) == len(real_chunks)


def test_real_chunk_ids_are_deterministic(real_chunks: list[Chunk]) -> None:
    again = chunk_articles(load_knowledge_base(KB_DIR), load_settings().chunking)
    assert [c.chunk_id for c in again] == [c.chunk_id for c in real_chunks]
    assert [c.text for c in again] == [c.text for c in real_chunks]
    assert "KB-001#pasos#0" in {c.chunk_id for c in real_chunks}


# --- Slugs -----------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("title", "slug"),
    [
        ("Síntoma", "sintoma"),
        ("Causa", "causa"),
        ("Pasos", "pasos"),
        ("Cuándo escalar", "cuando_escalar"),
        ("Introducción", "introduccion"),
        ("  Notas / Extra!! ", "notas_extra"),
    ],
)
def test_section_slug(title: str, slug: str) -> None:
    assert section_slug(title) == slug


def test_section_slug_rejects_titles_without_letters() -> None:
    with pytest.raises(ValueError, match="slug"):
        section_slug("¡¿?!")


# --- Chunks of one article ---------------------------------------------------------------


def test_one_chunk_per_short_section_with_metadata() -> None:
    article = _article(**{"Síntoma": "Algo falla.", "Cuándo escalar": "Escala como P3."})
    chunks = chunk_article(article, chunk_size=200, chunk_overlap=20)
    assert [c.chunk_id for c in chunks] == ["KB-900#sintoma#0", "KB-900#cuando_escalar#0"]
    assert chunks[1].text == "Artículo de prueba — Cuándo escalar\nEscala como P3."
    meta = chunks[0].metadata
    assert (meta.article_id, meta.categoria, meta.subcategoria, meta.idioma) == (
        "KB-900",
        "Accesos",
        "Prueba",
        "es",
    )
    assert meta.palabras_clave == "uno, dos"
    assert meta.source == "data/knowledge_base/KB-900.md"


def test_empty_optional_metadata_is_an_empty_string() -> None:
    article = _article().model_copy(update={"subcategoria": "", "palabras_clave": []})
    (chunk,) = chunk_article(article, chunk_size=200, chunk_overlap=20)
    assert chunk.metadata.subcategoria == "" and chunk.metadata.palabras_clave == ""


def test_long_section_is_split_with_sequential_ids() -> None:
    chunks = chunk_article(_article(Pasos=_words(60)), chunk_size=120, chunk_overlap=30)
    assert len(chunks) > 1
    assert [c.chunk_id for c in chunks] == [f"KB-900#pasos#{i}" for i in range(len(chunks))]
    assert all(c.text.startswith("Artículo de prueba — Pasos\n") for c in chunks)


def test_duplicate_section_slugs_are_rejected() -> None:
    article = _article(**{"Causa": "a", "causa": "b"})
    with pytest.raises(ValueError, match="KB-900#causa"):
        chunk_article(article, chunk_size=200, chunk_overlap=20)


def test_duplicate_chunk_ids_across_articles_are_rejected() -> None:
    config = ChunkingConfig(strategy="section", chunk_size=200, chunk_overlap=20)
    with pytest.raises(ValueError, match="duplicado"):
        chunk_articles([_article(), _article()], config)


@pytest.mark.parametrize(("size", "overlap"), [(0, 0), (100, 100), (100, -1)])
def test_invalid_sizes_are_rejected(size: int, overlap: int) -> None:
    with pytest.raises(ValueError, match="chunk"):
        chunk_article(_article(), chunk_size=size, chunk_overlap=overlap)


# --- split_text ----------------------------------------------------------------------------


def test_short_text_is_one_piece() -> None:
    assert split_text("  hola mundo \n", chunk_size=50, chunk_overlap=10) == ["hola mundo"]


def test_split_respects_size_overlap_and_word_boundaries() -> None:
    text = _words(80)
    pieces = split_text(text, chunk_size=100, chunk_overlap=25)
    words = set(text.split())
    assert len(pieces) > 1
    for piece in pieces:
        assert len(piece) <= 100
        assert set(piece.split()) <= words  # no word was cut in half
    for previous, current in zip(pieces, pieces[1:], strict=False):
        shared = [k for k in range(1, 26) if previous.endswith(current[:k])]
        assert shared, (previous, current)
        assert current.split()[0] in previous.split()
    assert pieces[0].split()[0] == "palabra000" and pieces[-1].split()[-1] == "palabra079"
    covered = [w for p in pieces for w in p.split()]
    assert set(covered) == words


def test_split_prefers_line_boundaries() -> None:
    lines = [f"{i}. Paso número {i} con algo de texto adicional." for i in range(1, 9)]
    pieces = split_text("\n".join(lines), chunk_size=120, chunk_overlap=20)
    assert len(pieces) > 1
    for piece in pieces:
        assert piece.splitlines()[-1] in lines  # every piece ends at a full line


def test_split_without_whitespace_cuts_hard_with_overlap() -> None:
    pieces = split_text("x" * 250, chunk_size=100, chunk_overlap=10)
    assert [len(p) for p in pieces] == [100, 100, 70]


def test_split_without_overlap_has_no_shared_text() -> None:
    text = _words(30)
    pieces = split_text(text, chunk_size=60, chunk_overlap=0)
    assert " ".join(pieces).split() == text.split()


def test_split_uses_a_line_break_right_after_the_window() -> None:
    text = "a" * 10 + "\n" + "b" * 10
    assert split_text(text, chunk_size=10, chunk_overlap=0) == ["a" * 10, "b" * 10]
