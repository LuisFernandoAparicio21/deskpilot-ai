"""Format checks of the 15 knowledge base articles in data/knowledge_base (S4, RF-11).

Each article is Markdown with a YAML front matter (fields of requirements section 11)
and four sections in a fixed order: Síntoma, Causa, Pasos, Cuándo escalar. The checks
also cover RN-01 (suggested priority), RN-03 (mandatory escalation for teller systems)
and RN-05 (articles never ask for passwords, PIN, tokens, card numbers or CURP).
"""

from __future__ import annotations

import datetime as dt
import re
from pathlib import Path
from typing import Any

import pytest
import yaml

from src.ingestion.ticket_catalog import KB_SUBCATEGORIES, SUBCATEGORIES

KB_DIR = Path(__file__).resolve().parents[2] / "data" / "knowledge_base"
ARTICLES = sorted(KB_DIR.glob("KB-*.md"))

REQUIRED_FIELDS = {
    "id",
    "titulo",
    "categoria",
    "subcategoria",
    "idioma",
    "fecha_actualizacion",
    "palabras_clave",
}
SECTIONS = ["Síntoma", "Causa", "Pasos", "Cuándo escalar"]
FILENAME_RE = re.compile(r"^KB-(\d{3})-[a-z0-9]+(?:-[a-z0-9]+)*\.md$")
STEP_RE = re.compile(r"^\d+\.\s+\S", re.MULTILINE)
PRIORITY_RE = re.compile(r"\bP[1-4]\b")

# RN-05: an explicit warning not to share the secret with anyone, support included.
WARNING_RE = re.compile(r"no compartas[^.]*con nadie[^.]*soporte", re.IGNORECASE)
WARNING_SUBCATEGORIES = {"Reseteo de contraseña", "Token bancario"}

# RN-05: imperative request verb + possessive + sensitive datum ("escribe tu contraseña").
SENSITIVE_REQUEST_RE = re.compile(
    r"\b(escribe|escriba|proporciona|proporcione|comparte|comparta|env[ií]a|env[ií]e|"
    r"dicta|dicte|indica|indique|captura|capture|confirma|confirme|danos|dame|dime|"
    r"pide|solicita|solicite)\b\s+(tu|su|el|la)\s+"
    r"(contraseña|nip|token|clave|código del token|número de tarjeta|curp)",
    re.IGNORECASE,
)

# RN-03: subcategories with a KB article that must always be escalated right away.
MANDATORY_ESCALATION = {s.name for s in SUBCATEGORIES if s.has_kb and s.escalation_rate == 1.0}


def _split(path: Path) -> tuple[dict[str, Any], str]:
    text = path.read_text(encoding="utf-8")
    match = re.match(r"^---\n(.*?)\n---\n(.*)$", text, re.DOTALL)
    assert match, f"{path.name}: falta el front matter YAML"
    meta = yaml.safe_load(match.group(1))
    assert isinstance(meta, dict), f"{path.name}: el front matter no es un mapa"
    return meta, match.group(2)


def _sections(body: str) -> dict[str, str]:
    parts = re.split(r"^## (.+)$", body, flags=re.MULTILINE)
    return {parts[i].strip(): parts[i + 1].strip() for i in range(1, len(parts), 2)}


def test_there_are_exactly_fifteen_articles() -> None:
    files = [p for p in KB_DIR.iterdir() if p.is_file()]
    assert len(files) == 15
    assert len(ARTICLES) == 15
    for path in ARTICLES:
        assert FILENAME_RE.match(path.name), path.name


@pytest.mark.parametrize("path", ARTICLES, ids=lambda p: p.stem)
def test_front_matter_has_all_fields(path: Path) -> None:
    meta, _ = _split(path)
    assert set(meta) >= REQUIRED_FIELDS
    assert meta["idioma"] == "es"
    assert meta["fecha_actualizacion"] == dt.date(2026, 11, 1)
    assert isinstance(meta["titulo"], str) and meta["titulo"].strip()
    keywords = meta["palabras_clave"]
    assert isinstance(keywords, list) and len(keywords) >= 5
    assert all(isinstance(k, str) and k.strip() for k in keywords)


def test_ids_are_unique_consecutive_and_match_filenames() -> None:
    ids = [_split(p)[0]["id"] for p in ARTICLES]
    assert ids == [f"KB-{n:03d}" for n in range(1, 16)]
    for path, article_id in zip(ARTICLES, ids, strict=True):
        assert path.name.startswith(f"{article_id}-")


def test_subcategories_match_catalog() -> None:
    metas = [_split(p)[0] for p in ARTICLES]
    assert sorted(m["subcategoria"] for m in metas) == sorted(KB_SUBCATEGORIES)
    categories = {s.name: s.categoria for s in SUBCATEGORIES}
    for meta in metas:
        assert meta["categoria"] == categories[meta["subcategoria"]], meta["id"]


@pytest.mark.parametrize("path", ARTICLES, ids=lambda p: p.stem)
def test_sections_in_order_and_not_empty(path: Path) -> None:
    _, body = _split(path)
    headings = re.findall(r"^## (.+)$", body, flags=re.MULTILINE)
    assert [h.strip() for h in headings] == SECTIONS
    for name, content in _sections(body).items():
        assert content, f"{path.name}: sección vacía {name}"


@pytest.mark.parametrize("path", ARTICLES, ids=lambda p: p.stem)
def test_steps_are_numbered(path: Path) -> None:
    _, body = _split(path)
    assert len(STEP_RE.findall(_sections(body)["Pasos"])) >= 3


@pytest.mark.parametrize("path", ARTICLES, ids=lambda p: p.stem)
def test_length_between_150_and_350_words(path: Path) -> None:
    _, body = _split(path)
    words = len(re.findall(r"\w+", body))
    assert 150 <= words <= 350, f"{path.name}: {words} palabras"


@pytest.mark.parametrize("path", ARTICLES, ids=lambda p: p.stem)
def test_escalation_suggests_priority(path: Path) -> None:
    _, body = _split(path)
    assert PRIORITY_RE.search(_sections(body)["Cuándo escalar"])


def test_password_and_token_articles_warn_not_to_share() -> None:
    found = set()
    for path in ARTICLES:
        meta, body = _split(path)
        if meta["subcategoria"] in WARNING_SUBCATEGORIES:
            assert WARNING_RE.search(body), path.name
            found.add(meta["subcategoria"])
    assert found == WARNING_SUBCATEGORIES


@pytest.mark.parametrize("path", ARTICLES, ids=lambda p: p.stem)
def test_no_sensitive_data_requests(path: Path) -> None:
    match = SENSITIVE_REQUEST_RE.search(path.read_text(encoding="utf-8"))
    assert match is None, f"{path.name}: {match.group(0) if match else ''}"


@pytest.mark.parametrize(
    "text",
    ["Escribe tu contraseña en el chat.", "Proporciona tu NIP.", "Indica su CURP."],
)
def test_sensitive_request_pattern_catches_requests(text: str) -> None:
    assert SENSITIVE_REQUEST_RE.search(text)


def test_mandatory_escalation_articles_escalate_always() -> None:
    assert MANDATORY_ESCALATION, "el catálogo debe tener al menos un caso RN-03 con artículo"
    for path in ARTICLES:
        meta, body = _split(path)
        if meta["subcategoria"] in MANDATORY_ESCALATION:
            escalation = _sections(body)["Cuándo escalar"]
            assert "SIEMPRE" in escalation and "inmediato" in escalation.lower(), path.name
