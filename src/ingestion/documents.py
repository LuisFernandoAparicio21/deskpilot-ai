"""Knowledge-base document loaders: Markdown, PDF and CSV (S7, RF-11).

Every loader returns ``KBArticle`` objects with the fields of requirements section 11
plus ``subcategoria``, ``palabras_clave`` and ``source_path``. ``secciones`` maps the
section title to its text, in document order, so the chunker can emit one chunk per
section.

- Markdown (``data/knowledge_base/KB-*.md``): YAML front matter between ``---`` lines and
  one section per ``##`` heading. Text before the first ``##`` (except the ``#`` title)
  is kept as the ``Introducción`` section, because it holds the RN-05 warnings.
- PDF: plain text of every page in a single ``Contenido`` section, with minimal
  metadata (id = file stem, title from the PDF metadata or the stem).
- CSV: one article per row; the section columns are ``sintoma``, ``causa``, ``pasos``
  and ``cuando_escalar`` and empty cells are skipped.

Any problem raises ``DocumentError`` with the file (and row) and what is missing.
"""

from __future__ import annotations

import csv
import datetime as dt
import logging
import re
from collections.abc import Callable, Iterable
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError
from pypdf import PdfReader
from pypdf.errors import PyPdfError

from src.utils.config import PROJECT_ROOT

logger = logging.getLogger(__name__)

SECTION_TITLES: tuple[str, ...] = ("Síntoma", "Causa", "Pasos", "Cuándo escalar")
INTRO_SECTION = "Introducción"
PDF_SECTION = "Contenido"
PDF_DEFAULT_CATEGORY = "General"

REQUIRED_FRONT_MATTER: tuple[str, ...] = (
    "id",
    "titulo",
    "categoria",
    "subcategoria",
    "idioma",
    "fecha_actualizacion",
    "palabras_clave",
)
CSV_SECTION_COLUMNS: dict[str, str] = {
    "sintoma": "Síntoma",
    "causa": "Causa",
    "pasos": "Pasos",
    "cuando_escalar": "Cuándo escalar",
}
CSV_REQUIRED_COLUMNS: tuple[str, ...] = (
    "id",
    "titulo",
    "categoria",
    "idioma",
    "fecha_actualizacion",
    *CSV_SECTION_COLUMNS,
)
CSV_COLUMNS: tuple[str, ...] = (
    "id",
    "titulo",
    "categoria",
    "subcategoria",
    "idioma",
    "fecha_actualizacion",
    "palabras_clave",
    *CSV_SECTION_COLUMNS,
)

_FRONT_MATTER_RE = re.compile(r"\A---\n(.*?)\n---[ \t]*(?:\n|\Z)(.*)\Z", re.DOTALL)
_HEADING_RE = re.compile(r"^##[ \t]+(.+?)[ \t]*$", re.MULTILINE)
_TITLE_LINE_RE = re.compile(r"^#[ \t]+.*$", re.MULTILINE)


class DocumentError(ValueError):
    """A knowledge-base document is missing, malformed or incomplete."""


class KBArticle(BaseModel):
    """One knowledge-base document ready to be chunked."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str = Field(min_length=1)
    titulo: str = Field(min_length=1)
    categoria: str = Field(min_length=1)
    subcategoria: str = ""
    idioma: str = Field(min_length=2)
    fecha_actualizacion: dt.date
    palabras_clave: list[str] = Field(default_factory=list)
    secciones: dict[str, str] = Field(min_length=1)
    source_path: str = Field(min_length=1)


def _display_path(path: Path) -> str:
    """Path relative to the repo root when possible, so ids and metadata are portable."""
    resolved = path.resolve()
    try:
        return resolved.relative_to(PROJECT_ROOT).as_posix()
    except ValueError:
        return resolved.as_posix()


def _read_text(path: Path) -> str:
    try:
        text = path.read_text(encoding="utf-8-sig")
    except (OSError, UnicodeDecodeError) as exc:
        raise DocumentError(f"{path}: no se pudo leer el archivo ({exc})") from exc
    return text.replace("\r\n", "\n").replace("\r", "\n")


def _keywords(value: Any, where: str) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        items: Iterable[Any] = re.split(r"[;,]", value)
    elif isinstance(value, list):
        items = value
    else:
        raise DocumentError(f"{where}: palabras_clave debe ser una lista o un texto")
    return [str(item).strip() for item in items if str(item).strip()]


def _build(where: str, **fields: Any) -> KBArticle:
    try:
        return KBArticle(**fields)
    except ValidationError as exc:
        problems = "; ".join(
            f"{'.'.join(str(p) for p in err['loc'])}: {err['msg']}" for err in exc.errors()
        )
        raise DocumentError(f"{where}: campos inválidos ({problems})") from exc


def _split_sections(body: str, where: str) -> dict[str, str]:
    parts = _HEADING_RE.split(body)
    if len(parts) < 3:
        raise DocumentError(f"{where}: no tiene secciones '## Título'")
    sections: dict[str, str] = {}
    intro = _TITLE_LINE_RE.sub("", parts[0]).strip()
    if intro:
        sections[INTRO_SECTION] = intro
    for title, text in zip(parts[1::2], parts[2::2], strict=True):
        if title in sections:
            raise DocumentError(f"{where}: sección duplicada: {title}")
        if not text.strip():
            raise DocumentError(f"{where}: sección vacía: {title}")
        sections[title] = text.strip()
    return sections


def load_markdown_article(path: Path | str) -> KBArticle:
    """Load a Markdown article with YAML front matter and ``##`` sections."""
    path = Path(path)
    where = str(path)
    match = _FRONT_MATTER_RE.match(_read_text(path))
    if match is None:
        raise DocumentError(f"{where}: falta el front matter YAML (bloque '---' al inicio)")
    try:
        meta = yaml.safe_load(match.group(1))
    except yaml.YAMLError as exc:
        raise DocumentError(f"{where}: front matter con YAML inválido ({exc})") from exc
    if not isinstance(meta, dict):
        raise DocumentError(f"{where}: el front matter no es un mapa clave: valor")
    missing = [name for name in REQUIRED_FRONT_MATTER if meta.get(name) in (None, "")]
    if missing:
        raise DocumentError(f"{where}: faltan campos: {', '.join(missing)}")
    return _build(
        where,
        id=str(meta["id"]).strip(),
        titulo=str(meta["titulo"]).strip(),
        categoria=str(meta["categoria"]).strip(),
        subcategoria=str(meta["subcategoria"]).strip(),
        idioma=str(meta["idioma"]).strip(),
        fecha_actualizacion=meta["fecha_actualizacion"],
        palabras_clave=_keywords(meta["palabras_clave"], where),
        secciones=_split_sections(match.group(2), where),
        source_path=_display_path(path),
    )


def load_pdf_document(path: Path | str, *, idioma: str = "es") -> KBArticle:
    """Load the plain text of a PDF into a single ``Contenido`` section."""
    path = Path(path)
    where = str(path)
    try:
        reader = PdfReader(path)
        text = "\n".join((page.extract_text() or "").strip() for page in reader.pages).strip()
        meta = reader.metadata
    except (OSError, PyPdfError) as exc:
        raise DocumentError(f"{where}: no se pudo leer el PDF ({exc})") from exc
    if not text:
        raise DocumentError(f"{where}: PDF sin texto extraíble")
    title = (meta.title or "").strip() if meta is not None else ""
    stamp = (meta.modification_date or meta.creation_date) if meta is not None else None
    if stamp is not None:
        updated = stamp.date()
    else:
        updated = dt.datetime.fromtimestamp(path.stat().st_mtime, tz=dt.UTC).date()
    return _build(
        where,
        id=path.stem,
        titulo=title or path.stem,
        categoria=PDF_DEFAULT_CATEGORY,
        subcategoria=PDF_DEFAULT_CATEGORY,
        idioma=idioma,
        fecha_actualizacion=updated,
        secciones={PDF_SECTION: text},
        source_path=_display_path(path),
    )


def load_csv_documents(path: Path | str) -> list[KBArticle]:
    """Load one article per CSV row (columns ``CSV_COLUMNS``; subcategory/keywords optional)."""
    path = Path(path)
    where = str(path)
    text = _read_text(path)
    reader = csv.DictReader(text.splitlines())
    if not reader.fieldnames:
        raise DocumentError(f"{where}: CSV vacío o sin encabezado")
    missing = [name for name in CSV_REQUIRED_COLUMNS if name not in reader.fieldnames]
    if missing:
        raise DocumentError(f"{where}: faltan columnas: {', '.join(missing)}")
    source = _display_path(path)
    articles = []
    for line, row in enumerate(reader, start=2):
        row_where = f"{where}, fila {line}"
        sections = {
            title: (row.get(column) or "").strip()
            for column, title in CSV_SECTION_COLUMNS.items()
            if (row.get(column) or "").strip()
        }
        if not sections:
            raise DocumentError(f"{row_where}: no tiene texto en ninguna sección")
        articles.append(
            _build(
                row_where,
                id=(row["id"] or "").strip(),
                titulo=(row["titulo"] or "").strip(),
                categoria=(row["categoria"] or "").strip(),
                subcategoria=(row.get("subcategoria") or "").strip(),
                idioma=(row["idioma"] or "").strip(),
                fecha_actualizacion=(row["fecha_actualizacion"] or "").strip(),
                palabras_clave=_keywords(row.get("palabras_clave"), row_where),
                secciones=sections,
                source_path=source,
            )
        )
    return articles


_LOADERS: dict[str, Callable[[Path], list[KBArticle]]] = {
    ".md": lambda p: [load_markdown_article(p)],
    ".pdf": lambda p: [load_pdf_document(p)],
    ".csv": load_csv_documents,
}


def load_knowledge_base(directory: Path | str) -> list[KBArticle]:
    """Load every ``.md``, ``.pdf`` and ``.csv`` file of a directory, sorted by id."""
    directory = Path(directory)
    if not directory.is_dir():
        raise DocumentError(f"{directory}: no es un directorio")
    articles: list[KBArticle] = []
    for path in sorted(directory.iterdir()):
        loader = _LOADERS.get(path.suffix.lower()) if path.is_file() else None
        if loader is None:
            logger.debug("Archivo ignorado en la base de conocimiento", extra={"path": str(path)})
            continue
        articles.extend(loader(path))
    seen: set[str] = set()
    for article in articles:
        if article.id in seen:
            raise DocumentError(f"{directory}: id duplicado: {article.id}")
        seen.add(article.id)
    articles.sort(key=lambda a: a.id)
    logger.info(
        "Base de conocimiento cargada",
        extra={"directory": _display_path(directory), "n_articles": len(articles)},
    )
    return articles
