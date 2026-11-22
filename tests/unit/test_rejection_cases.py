"""Format checks for the out-of-domain rejection cases (RN-04)."""

import csv
import re
from pathlib import Path

from src.api.evaluation import load_cases

EVAL_DIR = Path(__file__).resolve().parents[1] / "eval"
REJECTION = EVAL_DIR / "rejection_cases.csv"
CANONICAL = EVAL_DIR / "cases.csv"
COLUMNS = ["id", "pregunta", "intencion", "esperado", "obtenido", "resultado", "notas"]
ENGLISH = re.compile(r"\b(the|who|what|can|how|you|is|my|for)\b", re.IGNORECASE)
SPANISH = re.compile(r"[¿áéíóúñ]|\b(cómo|qué|cuál|el|la|los|mi)\b", re.IGNORECASE)
SENSITIVE = re.compile(
    r"(password\s*[:=]|api[_-]?key|secret|token\s*[:=]|\b\d{16}\b|[\w.]+@[\w.]+\.\w+)",
    re.IGNORECASE,
)


def _rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def test_header_matches_canonical_format() -> None:
    with REJECTION.open(encoding="utf-8-sig", newline="") as handle:
        assert next(csv.reader(handle)) == COLUMNS


def test_at_least_eight_cases_with_unique_rj_ids() -> None:
    ids = [r["id"] for r in _rows(REJECTION)]
    assert len(ids) >= 8
    assert len(set(ids)) == len(ids)
    assert all(re.fullmatch(r"RJ-\d{2}", i) for i in ids)


def test_all_cases_are_rejection_with_notes() -> None:
    for row in _rows(REJECTION):
        assert row["esperado"] == "rechazo", row["id"]
        assert row["notas"].strip(), row["id"]
        assert row["obtenido"] == "" and row["resultado"] == "", row["id"]


def test_mixes_spanish_and_english() -> None:
    spanish = english = 0
    for row in _rows(REJECTION):
        if SPANISH.search(row["pregunta"]):
            spanish += 1
        elif ENGLISH.search(row["pregunta"]):
            english += 1
    assert spanish >= 1 and english >= 1


def test_no_duplicates_with_canonical_cases() -> None:
    canonical = _rows(CANONICAL)
    new = _rows(REJECTION)
    assert not {r["id"] for r in new} & {r["id"] for r in canonical}
    assert not {r["pregunta"].strip().lower() for r in new} & {
        r["pregunta"].strip().lower() for r in canonical
    }
    questions = [r["pregunta"].strip().lower() for r in new]
    assert len(set(questions)) == len(questions)


def test_no_sensitive_data() -> None:
    for row in _rows(REJECTION):
        assert not SENSITIVE.search(" ".join(row.values())), row["id"]


def test_file_loads_with_load_cases() -> None:
    cases = load_cases(REJECTION)
    assert len(cases) == len(_rows(REJECTION))
