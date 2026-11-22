"""Unit tests: parsing and loading the evaluation cases (T21, S12)."""

from __future__ import annotations

import csv
from pathlib import Path

import pytest

from src.api.evaluation import (
    CaseError,
    EvalError,
    SearchOutcome,
    load_cases,
    parse_expected,
    run_cases,
)
from tests.unit.evalkit import (
    CASES_FILE,
    HEADER,
    PASSWORD,
    FakeBackend,
    _case,
    _clock,
    _run,
    _search,
    _ticket,
    _write_cases,
)

# --- parse_expected ----------------------------------------------------------------


@pytest.mark.parametrize(
    ("text", "kind"),
    [
        ("rechazo", "rechazo"),
        ("escalamiento", "escalamiento"),
        ("seguridad", "seguridad"),
        (" Rechazo ", "rechazo"),
        ("ARTICULO:KB-004", "articulo"),
    ],
)
def test_parse_expected_simple_kinds(text: str, kind: str) -> None:
    assert parse_expected(text).kind == kind


def test_parse_expected_article_normalizes_the_id() -> None:
    assert parse_expected("articulo: kb-004").article_id == "KB-004"


def test_parse_expected_ticket_fields() -> None:
    parsed = parse_expected("ticket:categoria=Accesos;prioridad=P1;subcategoria=VPN;escalado=TRUE")
    assert parsed.kind == "ticket"
    assert parsed.fields == {
        "categoria": "Accesos",
        "prioridad": "P1",
        "subcategoria": "VPN",
        "escalado": "TRUE",
    }


@pytest.mark.parametrize(
    "text",
    [
        "",
        "   ",
        "otro",
        "articulo",
        "articulo:",
        "articulo:KB-",
        "articulo:KB-4x",
        "articulo:XX-004",
        "rechazo:algo",
        "seguridad:x",
        "ticket",
        "ticket:",
        "ticket:prioridad",
        "ticket:prioridad=",
        "ticket:color=rojo",
        "ticket:prioridad=P1;prioridad=P2",
        "ticket:escalado=quizas",
        "ticket:prioridad=P1;;categoria=Accesos",
    ],
)
def test_parse_expected_rejects_invalid_values(text: str) -> None:
    with pytest.raises(ValueError):
        parse_expected(text)


# --- load_cases ---------------------------------------------------------------------


def test_load_cases_reads_valid_rows_and_trims(tmp_path: Path) -> None:
    path = _write_cases(
        tmp_path / "c.csv",
        [("A1", " VPN no conecta ", "vpn", "articulo:KB-004"), ("A2", "chiste", "x", "rechazo")],
    )
    cases = load_cases(path)
    assert [c.id for c in cases] == ["A1", "A2"]
    assert cases[0].pregunta == "VPN no conecta"
    assert cases[0].expectation.article_id == "KB-004"


def test_load_cases_accepts_bom_and_extra_columns(tmp_path: Path) -> None:
    path = tmp_path / "c.csv"
    path.write_text(
        "﻿id,pregunta,intencion,esperado,extra\nA1,hola,i,rechazo,zzz\n", encoding="utf-8"
    )
    assert load_cases(path)[0].id == "A1"


def test_load_cases_missing_file(tmp_path: Path) -> None:
    with pytest.raises(EvalError, match="cannot read"):
        load_cases(tmp_path / "nope.csv")


def test_load_cases_missing_columns_are_named(tmp_path: Path) -> None:
    path = tmp_path / "c.csv"
    path.write_text("id,pregunta\nA1,hola\n", encoding="utf-8")
    with pytest.raises(EvalError, match="intencion, esperado"):
        load_cases(path)


def test_load_cases_empty_file_and_header_only(tmp_path: Path) -> None:
    empty = tmp_path / "empty.csv"
    empty.write_text("", encoding="utf-8")
    with pytest.raises(EvalError):
        load_cases(empty)
    header_only = tmp_path / "h.csv"
    header_only.write_text(HEADER + "\n", encoding="utf-8")
    with pytest.raises(EvalError, match="no cases"):
        load_cases(header_only)


def test_load_cases_duplicate_id_names_the_row(tmp_path: Path) -> None:
    path = _write_cases(
        tmp_path / "c.csv", [("A1", "p", "i", "rechazo"), ("A1", "q", "i", "rechazo")]
    )
    with pytest.raises(EvalError, match=r"row 3.*duplicate id A1"):
        load_cases(path)


@pytest.mark.parametrize(("case_id", "question"), [("", "p"), ("A1", ""), ("A1", "   ")])
def test_load_cases_requires_id_and_question(tmp_path: Path, case_id: str, question: str) -> None:
    path = _write_cases(tmp_path / "c.csv", [(case_id, question, "i", "rechazo")])
    with pytest.raises(EvalError, match="required"):
        load_cases(path)


def test_load_cases_invalid_expected_names_row_and_id(tmp_path: Path) -> None:
    path = _write_cases(
        tmp_path / "c.csv", [("A1", "p", "i", "rechazo"), ("A2", "p", "i", "articulo:KB-X")]
    )
    with pytest.raises(EvalError, match=r"row 3 \(A2\)"):
        load_cases(path)


# --- run_cases: verdict per kind -------------------------------------------------------


def test_article_case_needs_the_article_in_top3_and_status_answered() -> None:
    case = _case("A", "articulo:KB-004")
    assert _run(case, FakeBackend(lambda q: _search("answered", ["KB-001", "KB-004"]))).passed
    wrong = _run(case, FakeBackend(lambda q: _search("answered", ["KB-001", "KB-002"])))
    assert not wrong.passed
    assert "KB-004" in wrong.notas
    assert not _run(case, FakeBackend(lambda q: _search("no_evidence", ["KB-004"]))).passed
    assert not _run(case, FakeBackend(lambda q: _search("mandatory_escalation", ["KB-004"]))).passed


def test_rechazo_and_escalamiento_check_the_status() -> None:
    reject, escalate = _case("R", "rechazo"), _case("E", "escalamiento")
    assert _run(reject, FakeBackend(lambda q: _search("no_evidence", []))).passed
    assert not _run(reject, FakeBackend(lambda q: _search("answered"))).passed
    assert not _run(reject, FakeBackend(lambda q: _search("mandatory_escalation"))).passed
    assert _run(escalate, FakeBackend(lambda q: _search("mandatory_escalation"))).passed
    assert not _run(escalate, FakeBackend(lambda q: _search("answered"))).passed


def test_ticket_case_compares_every_key_ignoring_case() -> None:
    case = _case("T", "ticket:categoria=accesos;prioridad=p1;escalado=FALSE")
    assert _run(case, FakeBackend(ticket_fn=lambda q: _ticket("Accesos", "P1", False))).passed
    bad = _run(case, FakeBackend(ticket_fn=lambda q: _ticket("Accesos", "P2", False)))
    assert not bad.passed
    assert "prioridad: esperado p1, obtenido P2" in bad.notas
    assert not _run(case, FakeBackend(ticket_fn=lambda q: _ticket("Accesos", "P1", True))).passed


def test_ticket_case_uses_the_question_as_description() -> None:
    backend = FakeBackend()
    _run(_case("T", "ticket:prioridad=P2", "No puedo entrar a SAP"), backend)
    assert backend.questions == ["No puedo entrar a SAP"]


def test_case_error_fails_only_that_case_and_the_run_continues() -> None:
    def search(q: str) -> SearchOutcome:
        if "boom" in q:
            raise CaseError("http 500")
        return _search("no_evidence", [])

    cases = [_case("A", "rechazo", "boom"), _case("B", "rechazo", "ok")]
    report = run_cases(cases, FakeBackend(search), "fake", _clock())
    assert [r.passed for r in report.results] == [False, True]
    assert report.results[0].notas == "http 500"


def test_unexpected_exception_is_reported_by_type_only() -> None:
    def search(q: str) -> SearchOutcome:
        raise RuntimeError(f"leaked {PASSWORD}")

    result = _run(_case("A", "rechazo", f"mi contraseña es {PASSWORD}"), FakeBackend(search))
    assert not result.passed
    assert result.notas == "unexpected RuntimeError"
    assert PASSWORD not in result.notas + result.obtenido


def test_eval_error_aborts_the_run() -> None:
    def search(q: str) -> SearchOutcome:
        raise EvalError("API down")

    with pytest.raises(EvalError):
        run_cases([_case("A", "rechazo")], FakeBackend(search), "fake", _clock())


# --- the real cases file ----------------------------------------------------------------


def test_cases_file_has_30_valid_cases_covering_the_requirements() -> None:
    cases = load_cases(CASES_FILE)
    kinds = [c.expectation.kind for c in cases]
    articles = {c.expectation.article_id for c in cases if c.expectation.kind == "articulo"}
    assert len(cases) == 30
    assert kinds.count("articulo") >= 12
    assert kinds.count("rechazo") >= 4
    assert kinds.count("escalamiento") >= 4
    assert kinds.count("ticket") >= 5
    assert kinds.count("seguridad") >= 3
    assert len(articles) >= 12
    assert len({c.pregunta for c in cases}) == 30


def test_cases_file_has_the_documented_columns_and_empty_result_columns() -> None:
    with CASES_FILE.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        assert reader.fieldnames == HEADER.split(",")
        rows = list(reader)
    assert all(r["obtenido"] == "" and r["resultado"] == "" for r in rows)
