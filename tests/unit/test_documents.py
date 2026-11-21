"""Unit tests for src/ingestion/documents.py (S7, RF-11)."""

from __future__ import annotations

import csv
import datetime as dt
from pathlib import Path

import pytest
from pypdf import PdfWriter

from src.ingestion.documents import (
    CSV_COLUMNS,
    SECTION_TITLES,
    DocumentError,
    KBArticle,
    load_csv_documents,
    load_knowledge_base,
    load_markdown_article,
    load_pdf_document,
)

KB_DIR = Path(__file__).resolve().parents[2] / "data" / "knowledge_base"

VALID_MD = """---
id: KB-900
titulo: Artículo de prueba
categoria: Accesos
subcategoria: Prueba
idioma: es
fecha_actualizacion: 2026-11-01
palabras_clave:
  - prueba
  - test
---

# Artículo de prueba

> Aviso previo.

## Síntoma

Algo falla.

## Causa

Una causa.

## Pasos

1. Paso uno.

## Cuándo escalar

Escala como P3.
"""


def _write(path: Path, text: str) -> Path:
    path.write_bytes(text.encode("utf-8"))
    return path


def _write_text_pdf(path: Path, lines: list[str], title: str | None = None) -> Path:
    """Write a minimal one-page PDF with real text (hand-made xref, no binary fixture)."""
    ops = " ".join(f"({line}) Tj 0 -16 Td" for line in lines)
    content = f"BT /F1 12 Tf 72 720 Td {ops} ET".encode("ascii")
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R "
        b"/Resources << /Font << /F1 5 0 R >> >> >>",
        b"<< /Length %d >>\nstream\n" % len(content) + content + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    if title is not None:
        objects.append(f"<< /Title ({title}) /ModDate (D:20261015120000) >>".encode("ascii"))
    out = bytearray(b"%PDF-1.4\n")
    offsets = []
    for number, body in enumerate(objects, start=1):
        offsets.append(len(out))
        out += b"%d 0 obj\n" % number + body + b"\nendobj\n"
    xref = len(out)
    out += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objects) + 1)
    out += b"".join(b"%010d 00000 n \n" % offset for offset in offsets)
    info = b" /Info 6 0 R" if title is not None else b""
    out += b"trailer\n<< /Size %d /Root 1 0 R%s >>\n" % (len(objects) + 1, info)
    out += b"startxref\n%d\n%%%%EOF\n" % xref
    path.write_bytes(bytes(out))
    return path


def _write_csv(path: Path, rows: list[dict[str, str]], columns: tuple[str, ...]) -> Path:
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(columns))
        writer.writeheader()
        writer.writerows(rows)
    return path


def _csv_row(**overrides: str) -> dict[str, str]:
    row = {
        "id": "KB-950",
        "titulo": "Artículo CSV",
        "categoria": "Software",
        "subcategoria": "Prueba CSV",
        "idioma": "en",
        "fecha_actualizacion": "2026-10-01",
        "palabras_clave": "csv; prueba ;",
        "sintoma": "Symptom text.",
        "causa": "Cause text.",
        "pasos": "1. Step.",
        "cuando_escalar": "",
    }
    row.update(overrides)
    return row


# --- Real knowledge base -------------------------------------------------------------


@pytest.fixture(scope="module")
def real_articles() -> list[KBArticle]:
    return load_knowledge_base(KB_DIR)


def test_real_knowledge_base_loads_fifteen_articles_sorted(real_articles: list[KBArticle]) -> None:
    assert [a.id for a in real_articles] == [f"KB-{n:03d}" for n in range(1, 16)]


def test_real_articles_have_all_fields_and_sections(real_articles: list[KBArticle]) -> None:
    for article in real_articles:
        assert article.titulo and article.categoria and article.subcategoria
        assert article.idioma == "es"
        assert article.fecha_actualizacion == dt.date(2026, 11, 1)
        assert article.palabras_clave and all(article.palabras_clave)
        for title in SECTION_TITLES:
            assert article.secciones[title].strip(), (article.id, title)
        assert article.source_path.startswith("data/knowledge_base/KB-")
        assert not any(text.startswith("#") for text in article.secciones.values())


def test_preamble_warning_is_kept_as_introduction(real_articles: list[KBArticle]) -> None:
    by_id = {a.id: a for a in real_articles}
    assert "No compartas tu contraseña" in by_id["KB-001"].secciones["Introducción"]
    assert list(by_id["KB-001"].secciones)[0] == "Introducción"
    assert "Introducción" not in by_id["KB-004"].secciones


# --- Markdown --------------------------------------------------------------------------


def test_markdown_article_parses_front_matter_and_sections(tmp_path: Path) -> None:
    article = load_markdown_article(_write(tmp_path / "a.md", VALID_MD))
    assert article.id == "KB-900"
    assert article.palabras_clave == ["prueba", "test"]
    assert list(article.secciones) == ["Introducción", *SECTION_TITLES]
    assert article.secciones["Introducción"] == "> Aviso previo."
    assert article.secciones["Pasos"] == "1. Paso uno."


def test_markdown_accepts_crlf_bom_and_comma_keywords(tmp_path: Path) -> None:
    text = VALID_MD.replace("  - prueba\n  - test\n", "").replace(
        "palabras_clave:", "palabras_clave: uno, dos ,"
    )
    path = tmp_path / "crlf.md"
    path.write_bytes(b"\xef\xbb\xbf" + text.replace("\n", "\r\n").encode("utf-8"))
    article = load_markdown_article(path)
    assert article.palabras_clave == ["uno", "dos"]
    assert article.secciones["Causa"] == "Una causa."


@pytest.mark.parametrize(
    ("text", "message"),
    [
        ("# Sin front matter\n\n## Síntoma\n\nx\n", "falta el front matter"),
        ("---\nid: [sin cerrar\n---\n## Síntoma\nx\n", "YAML inválido"),
        ("---\n- lista\n---\n## Síntoma\nx\n", "no es un mapa"),
        (VALID_MD.replace("categoria: Accesos\n", ""), "faltan campos: categoria"),
        (VALID_MD.split("## Síntoma")[0], "no tiene secciones"),
        (VALID_MD.replace("Una causa.", ""), "sección vacía: Causa"),
        (VALID_MD.replace("## Pasos", "## Causa"), "sección duplicada: Causa"),
        (VALID_MD.replace("2026-11-01", "no-es-fecha"), "fecha_actualizacion"),
        (VALID_MD.replace("palabras_clave:", "palabras_clave: 3\nx:"), "palabras_clave"),
    ],
)
def test_markdown_errors_are_clear(tmp_path: Path, text: str, message: str) -> None:
    path = _write(tmp_path / "bad.md", text)
    with pytest.raises(DocumentError, match=message) as info:
        load_markdown_article(path)
    assert "bad.md" in str(info.value)


def test_markdown_missing_file_raises_document_error(tmp_path: Path) -> None:
    with pytest.raises(DocumentError, match="no se pudo leer"):
        load_markdown_article(tmp_path / "missing.md")


# --- PDF -------------------------------------------------------------------------------


def test_pdf_text_goes_to_contenido_with_metadata_title(tmp_path: Path) -> None:
    path = _write_text_pdf(
        tmp_path / "guia-vpn.pdf", ["Reinicia el router", "Segunda linea"], "Guia VPN"
    )
    article = load_pdf_document(path)
    assert article.id == "guia-vpn"
    assert article.titulo == "Guia VPN"
    assert article.secciones == {"Contenido": "Reinicia el router\nSegunda linea"}
    assert article.fecha_actualizacion == dt.date(2026, 10, 15)
    assert article.idioma == "es"
    assert article.categoria == article.subcategoria == "General"


def test_pdf_without_metadata_uses_file_stem(tmp_path: Path) -> None:
    article = load_pdf_document(_write_text_pdf(tmp_path / "manual.pdf", ["Hola"]), idioma="en")
    assert article.titulo == "manual"
    assert article.idioma == "en"
    assert article.secciones["Contenido"] == "Hola"


def test_pdf_without_text_raises(tmp_path: Path) -> None:
    writer = PdfWriter()
    writer.add_blank_page(width=612, height=792)
    path = tmp_path / "blank.pdf"
    with path.open("wb") as fh:
        writer.write(fh)
    with pytest.raises(DocumentError, match="sin texto extraíble"):
        load_pdf_document(path)


def test_corrupt_pdf_raises(tmp_path: Path) -> None:
    path = _write(tmp_path / "broken.pdf", "esto no es un PDF")
    with pytest.raises(DocumentError, match="broken.pdf"):
        load_pdf_document(path)


# --- CSV -------------------------------------------------------------------------------


def test_csv_rows_become_articles(tmp_path: Path) -> None:
    rows = [_csv_row(), _csv_row(id="KB-951", cuando_escalar="Escala como P2.")]
    path = _write_csv(tmp_path / "kb.csv", rows, CSV_COLUMNS)
    first, second = load_csv_documents(path)
    assert first.id == "KB-950" and first.idioma == "en"
    assert first.palabras_clave == ["csv", "prueba"]
    assert list(first.secciones) == ["Síntoma", "Causa", "Pasos"]
    assert second.secciones["Cuándo escalar"] == "Escala como P2."
    assert first.source_path == second.source_path


def test_csv_optional_columns_default(tmp_path: Path) -> None:
    columns = tuple(c for c in CSV_COLUMNS if c not in {"subcategoria", "palabras_clave"})
    row = {k: v for k, v in _csv_row().items() if k in columns}
    (article,) = load_csv_documents(_write_csv(tmp_path / "kb.csv", [row], columns))
    assert article.subcategoria == "" and article.palabras_clave == []


def test_csv_missing_column_raises(tmp_path: Path) -> None:
    columns = tuple(c for c in CSV_COLUMNS if c != "titulo")
    row = {k: v for k, v in _csv_row().items() if k in columns}
    with pytest.raises(DocumentError, match="faltan columnas: titulo"):
        load_csv_documents(_write_csv(tmp_path / "kb.csv", [row], columns))


@pytest.mark.parametrize(
    ("override", "message"),
    [
        ({"sintoma": "", "causa": "", "pasos": ""}, "fila 2: no tiene texto en ninguna sección"),
        ({"fecha_actualizacion": "ayer"}, "fila 2: .*fecha_actualizacion"),
        ({"id": ""}, "fila 2: .*id"),
    ],
)
def test_csv_invalid_rows_raise(tmp_path: Path, override: dict[str, str], message: str) -> None:
    path = _write_csv(tmp_path / "kb.csv", [_csv_row(**override)], CSV_COLUMNS)
    with pytest.raises(DocumentError, match=message):
        load_csv_documents(path)


def test_csv_without_header_raises(tmp_path: Path) -> None:
    with pytest.raises(DocumentError, match="vacío"):
        load_csv_documents(_write(tmp_path / "empty.csv", ""))


# --- Directory -------------------------------------------------------------------------


def test_load_knowledge_base_dispatches_by_extension(tmp_path: Path) -> None:
    _write(tmp_path / "z.md", VALID_MD)
    _write_text_pdf(tmp_path / "A-guia.pdf", ["Texto"])
    _write_csv(tmp_path / "extra.CSV", [_csv_row()], CSV_COLUMNS)
    _write(tmp_path / "notas.txt", "se ignora")
    (tmp_path / "subdir").mkdir()
    articles = load_knowledge_base(tmp_path)
    assert [a.id for a in articles] == ["A-guia", "KB-900", "KB-950"]


def test_load_knowledge_base_rejects_duplicate_ids(tmp_path: Path) -> None:
    _write(tmp_path / "a.md", VALID_MD)
    _write(tmp_path / "b.md", VALID_MD)
    with pytest.raises(DocumentError, match="id duplicado: KB-900"):
        load_knowledge_base(tmp_path)


def test_load_knowledge_base_requires_directory(tmp_path: Path) -> None:
    with pytest.raises(DocumentError, match="no es un directorio"):
        load_knowledge_base(tmp_path / "missing")
