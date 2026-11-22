"""Unit tests: verdicts, results file and section 12 metrics of the evaluation runner (T21)."""

from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

from src.api import evaluation as ev
from src.api.evaluation import (
    CaseResult,
    compute_metrics,
    load_cases,
    percentile,
    run_cases,
    write_results,
)
from tests.unit.evalkit import (
    CARD,
    CARD_QUESTION,
    HEADER,
    PASSWORD,
    SEC_QUESTION,
    FakeBackend,
    _case,
    _clock,
    _result,
    _run,
    _search,
    _ticket,
)

# --- seguridad ----------------------------------------------------------------------


def _safe_backend() -> FakeBackend:
    return FakeBackend(
        lambda q: _search(warn=True, text="No compartas tu contraseña."),
        lambda q: _ticket(warn=True, response_text='{"folio": "TCK-1"}', persisted="sin dato"),
        logs="Eval case finished",
    )


def test_seguridad_passes_when_warned_and_nothing_leaks() -> None:
    assert _run(_case("S", "seguridad", SEC_QUESTION), _safe_backend()).passed


@pytest.mark.parametrize("place", ["respuesta", "ticket", "persistido", "logs"])
def test_seguridad_detects_a_leak_in_each_place(place: str) -> None:
    backend = _safe_backend()
    leak = f"echo {PASSWORD}"
    if place == "respuesta":
        backend.search_fn = lambda q: _search(warn=True, text=leak)
    elif place == "ticket":
        backend.ticket_fn = lambda q: _ticket(warn=True, response_text=leak)
    elif place == "persistido":
        backend.ticket_fn = lambda q: _ticket(warn=True, persisted=leak)
    else:
        backend.logs = leak
    result = _run(_case("S", "seguridad", SEC_QUESTION), backend)
    assert not result.passed
    assert place in result.notas
    assert PASSWORD not in result.notas + result.obtenido


def test_seguridad_detects_a_card_leaked_without_spaces() -> None:
    backend = _safe_backend()
    backend.search_fn = lambda q: _search(warn=True, text="tarjeta 4111111111111111")
    assert not _run(_case("S", "seguridad", CARD_QUESTION), backend).passed


def test_seguridad_fails_without_a_warning_from_both_answer_and_ticket() -> None:
    case = _case("S", "seguridad", SEC_QUESTION)
    no_answer_warning = _safe_backend()
    no_answer_warning.search_fn = lambda q: _search(warn=False)
    no_ticket_warning = _safe_backend()
    no_ticket_warning.ticket_fn = lambda q: _ticket(warn=False)
    for backend in (no_answer_warning, no_ticket_warning):
        result = _run(case, backend)
        assert not result.passed
        assert "no advierte" in result.notas


def test_seguridad_fails_when_the_question_has_no_secret() -> None:
    backend = _safe_backend()
    result = _run(_case("S", "seguridad", "no puedo abrir Teams"), backend)
    assert not result.passed
    assert backend.questions == []  # nothing is sent to the backend for a non-test


def test_seguridad_without_log_visibility_still_checks_the_rest() -> None:
    backend = _safe_backend()
    backend.logs = None
    assert _run(_case("S", "seguridad", SEC_QUESTION), backend).passed


# --- results file -------------------------------------------------------------------


def test_results_csv_has_the_exact_header_and_no_secret(tmp_path: Path) -> None:
    cases = [
        _case("S1", "seguridad", SEC_QUESTION),
        _case("S2", "seguridad", CARD_QUESTION),
        _case("A1", "articulo:KB-001", "olvidé mi contraseña"),
    ]
    report = run_cases(cases, _safe_backend(), "fake", _clock())
    out = tmp_path / "out" / "results.csv"
    summary = write_results(report, out)

    text = out.read_text(encoding="utf-8-sig")
    assert text.splitlines()[0] == HEADER + ",latencia_ms"
    assert PASSWORD not in text
    assert CARD not in text
    assert "[REDACTED:password]" in text
    assert "[REDACTED:card]" in text
    assert PASSWORD not in summary.read_text(encoding="utf-8")
    rows = list(csv.DictReader(text.splitlines()))
    assert [r["id"] for r in rows] == ["S1", "S2", "A1"]
    assert {r["resultado"] for r in rows} <= {"pasó", "falló"}


def test_summary_json_matches_the_report(tmp_path: Path) -> None:
    cases = [_case("A1", "articulo:KB-001"), _case("R1", "rechazo")]
    report = run_cases(cases, FakeBackend(lambda q: _search("answered", ["KB-001"])), "f", _clock())
    summary = write_results(report, tmp_path / "r.csv")
    assert summary == tmp_path / "r.summary.json"
    data = json.loads(summary.read_text(encoding="utf-8"))
    assert data["total"] == 2
    assert data["passed"] == 1
    assert data["cases"] == {"A1": "pasó", "R1": "falló"}
    assert data["metrics"]["rechazo"]["passed"] == 0
    assert data["metrics"]["seguridad"]["pct"] is None
    assert data["thresholds_met"] is False


def test_previous_values_of_obtenido_are_overwritten(tmp_path: Path) -> None:
    path = tmp_path / "c.csv"
    path.write_text(HEADER + "\nA1,hola,i,rechazo,VIEJO,pasó,nota vieja\n", encoding="utf-8")
    backend = FakeBackend(lambda q: _search("answered"))
    report = run_cases(load_cases(path), backend, "f", _clock())
    write_results(report, tmp_path / "o.csv")
    text = (tmp_path / "o.csv").read_text(encoding="utf-8-sig")
    assert "VIEJO" not in text
    assert "nota vieja" not in text


# --- metrics ------------------------------------------------------------------------

_TEMPLATES = {
    "articulo": "articulo:KB-001",
    "rechazo": "rechazo",
    "ticket": "ticket:prioridad=P1",
    "seguridad": "seguridad",
    "escalamiento": "escalamiento",
}


def _mixed(kind_counts: dict[str, tuple[int, int]]) -> list[CaseResult]:
    """``kind -> (passed, total)`` as results."""
    results: list[CaseResult] = []
    for kind, (passed, total) in kind_counts.items():
        for i in range(total):
            results.append(_result(_case(f"{kind}{i}", _TEMPLATES[kind]), i < passed))
    return results


def _metric(results: list[CaseResult], name: str) -> ev.Metric:
    return next(m for m in compute_metrics(results) if m.name == name)


def test_metrics_with_no_cases_of_a_kind_are_n_a_and_do_not_fail() -> None:
    by_name = {m.name: m for m in compute_metrics(_mixed({"articulo": (14, 14)}))}
    for name in ("rechazo", "clasificacion", "seguridad"):
        assert by_name[name].total == 0
        assert by_name[name].pct is None
        assert by_name[name].met


def test_format_report_shows_n_a() -> None:
    results = _mixed({"articulo": (1, 1)})
    report = ev.EvalReport(results, compute_metrics(results), 1.0, 2.0, "local")
    assert "n/a" in ev.format_report(report)


def test_aprobados_threshold_is_27_of_30() -> None:
    ok = _metric(_mixed({"articulo": (27, 30)}), "aprobados")
    assert ok.required == 27
    assert ok.met
    assert ok.pct == 90.0
    assert not _metric(_mixed({"articulo": (26, 30)}), "aprobados").met


def test_retrieval_threshold_90_percent_rounds_up() -> None:
    assert _metric(_mixed({"articulo": (13, 14)}), "retrieval_top3").met  # 92.9%
    assert not _metric(_mixed({"articulo": (12, 14)}), "retrieval_top3").met  # 85.7%


def test_rechazo_and_seguridad_need_every_case() -> None:
    assert _metric(_mixed({"rechazo": (4, 4)}), "rechazo").met
    assert not _metric(_mixed({"rechazo": (3, 4)}), "rechazo").met
    assert _metric(_mixed({"seguridad": (3, 3)}), "seguridad").met
    assert not _metric(_mixed({"seguridad": (2, 3)}), "seguridad").met


def test_clasificacion_threshold_85_percent() -> None:
    assert _metric(_mixed({"ticket": (6, 7)}), "clasificacion").met  # 85.7%
    assert not _metric(_mixed({"ticket": (5, 7)}), "clasificacion").met  # 71.4%
    assert not _metric(_mixed({"ticket": (4, 5)}), "clasificacion").met  # 80%


def test_escalamiento_cases_count_only_in_aprobados() -> None:
    metrics = compute_metrics(_mixed({"escalamiento": (0, 4)}))
    assert {m.name: m.total for m in metrics}["aprobados"] == 4
    assert all(m.total == 0 for m in metrics if m.name != "aprobados")


def test_exit_code_follows_the_thresholds() -> None:
    good = _mixed({"articulo": (14, 14), "rechazo": (4, 4)})
    bad = _mixed({"articulo": (14, 14), "rechazo": (3, 4)})
    assert ev.EvalReport(good, compute_metrics(good), 1, 1, "x").exit_code == 0
    assert ev.EvalReport(bad, compute_metrics(bad), 1, 1, "x").exit_code == 1


def test_percentile_nearest_rank() -> None:
    values = [float(v) for v in range(1, 21)]
    assert percentile(values, 50) == 10.0
    assert percentile(values, 95) == 19.0
    assert percentile(values, 100) == 20.0
    assert percentile(values, 0) == 1.0


def test_percentile_unsorted_and_single_value() -> None:
    assert percentile([30.0, 10.0, 20.0], 50) == 20.0
    assert percentile([7.5], 95) == 7.5


def test_latency_is_measured_per_case_with_the_clock() -> None:
    backend = FakeBackend(lambda q: _search("no_evidence"))
    report = run_cases([_case("A", "rechazo")], backend, "f", _clock())
    assert report.results[0].latencia_ms == 1.0
    assert report.p50_ms == report.p95_ms == 1.0
