"""Exit-code contract of ``main.py eval`` (0/1/2/3), EvalConfig validation and ci.yml."""

from __future__ import annotations

import json
import re
import sqlite3
from collections.abc import Callable, Iterator
from contextlib import closing, contextmanager
from pathlib import Path
from typing import Any

import pytest
import yaml
from pydantic import ValidationError

import main
from src.api import evaluation as ev
from src.api.evaluation import SearchOutcome, TicketOutcome
from src.utils.config import (
    PROJECT_ROOT,
    ConfigError,
    EvalConfig,
    EvalThresholds,
    KnownFailure,
    Settings,
    load_settings,
)
from src.utils.logging import shutdown_logging
from tests.unit.evalkit import PASSWORD, FakeBackend, _search, _ticket

SEC_Q = f"No entro al correo, mi contraseña es {PASSWORD}"
CI = PROJECT_ROOT / ".github" / "workflows" / "ci.yml"

# --- EvalConfig validation (invalid => ConfigError => exit 2) ----------------------------


@pytest.mark.parametrize("field", list(EvalThresholds.model_fields))
@pytest.mark.parametrize("value", [-0.1, 100.1, 101, -5])
def test_thresholds_outside_0_100_are_rejected(field: str, value: float) -> None:
    with pytest.raises(ValidationError):
        EvalThresholds(**{field: value})


@pytest.mark.parametrize("value", [0, 50.5, 100])
def test_thresholds_accept_the_range_bounds(value: float) -> None:
    assert EvalThresholds(min_passed=value).min_passed == value


@pytest.mark.parametrize("bad_id", ["EV16", "ev-16", "EV-1", "EV-", "X-16", "EV-16 ", "EV-1a", ""])
def test_known_failure_id_format(bad_id: str) -> None:
    with pytest.raises(ValidationError):
        KnownFailure(id=bad_id, reason="why")


@pytest.mark.parametrize("reason", ["", "   ", "\t\n"])
def test_known_failure_reason_must_not_be_blank(reason: str) -> None:
    with pytest.raises(ValidationError):
        KnownFailure(id="EV-16", reason=reason)


def test_duplicate_known_failure_ids_are_rejected() -> None:
    with pytest.raises(ValidationError, match="duplicate ids: EV-16"):
        EvalConfig(
            known_failures=[
                KnownFailure(id="EV-16", reason="a"),
                KnownFailure(id="EV-16", reason="b"),
            ]
        )


def test_unknown_eval_keys_are_rejected() -> None:
    with pytest.raises(ValidationError):
        EvalConfig.model_validate({"thresholds": {"min_pased": 90}})


def _bad_config(tmp_path: Path, mutate: Callable[[dict[str, Any]], None]) -> Path:
    data = yaml.safe_load((PROJECT_ROOT / "config.yaml").read_text(encoding="utf-8"))
    mutate(data)
    path = tmp_path / "config.yaml"
    path.write_text(yaml.safe_dump(data, allow_unicode=True), encoding="utf-8")
    return path


@pytest.mark.parametrize(
    "mutate",
    [
        lambda d: d["eval"]["thresholds"].update(security_pct=101),
        lambda d: d["eval"]["thresholds"].update(min_passed=-1),
        lambda d: d["eval"].update(known_failures=[{"id": "16", "reason": "x"}]),
        lambda d: d["eval"].update(known_failures=[{"id": "EV-16", "reason": " "}]),
        lambda d: d["eval"].update(
            known_failures=[{"id": "EV-16", "reason": "a"}, {"id": "EV-16", "reason": "b"}]
        ),
    ],
)
def test_invalid_eval_config_is_a_config_error_and_exit_2(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    mutate: Callable[[dict[str, Any]], None],
) -> None:
    path = _bad_config(tmp_path, mutate)
    env = tmp_path / "missing.env"
    with pytest.raises(ConfigError):
        load_settings(path, env_file=env)
    monkeypatch.setattr(main, "load_settings", lambda: load_settings(path, env_file=env))
    code = main.main(["eval", "--cases", str(tmp_path / "c.csv"), "--out", str(tmp_path / "o.csv")])
    assert code == 2
    assert "eval" in capsys.readouterr().err
    assert not (tmp_path / "o.csv").exists()


def test_repo_config_has_ev16_as_the_only_known_failure(tmp_path: Path) -> None:
    cfg = load_settings(env_file=tmp_path / "missing.env").eval
    assert [k.id for k in cfg.known_failures] == ["EV-16"]
    assert cfg.known_failures[0].reason.strip()


# --- exit-code matrix with synthetic cases ---------------------------------------------------
# 16 cases: EV-01..10 articulo, EV-11 ticket, EV-12 seguridad, EV-13..16 rechazo.
# Default thresholds: min_passed 90% of 16 => at most 1 failure; retrieval 9/10.

ARTICLES = [f"EV-{i:02d}" for i in range(1, 11)]
REJECTS = [f"EV-{i:02d}" for i in range(13, 17)]
ALL_IDS = [*ARTICLES, "EV-11", "EV-12", *REJECTS]


def _write_matrix_cases(path: Path, ids: list[str] | None = None) -> Path:
    rows: list[tuple[str, str, str]] = []
    rows += [(i, f"q-{i}", "articulo:KB-004") for i in ARTICLES]
    rows += [("EV-11", "q-EV-11", "ticket:prioridad=P2"), ("EV-12", SEC_Q, "seguridad")]
    rows += [(i, f"q-{i}", "rechazo") for i in REJECTS]
    if ids is not None:
        rows = [r for r in rows if r[0] in ids]
    lines = ["id,pregunta,intencion,esperado,obtenido,resultado,notas"]
    lines += [f'"{i}","{q}","i","{e}","","",""' for i, q, e in rows]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


class Run:
    def __init__(self, code: int, out: str, err: str, summary: dict[str, Any]) -> None:
        self.code, self.out, self.err, self.summary = code, out, err, summary


@pytest.fixture
def run_matrix(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> Iterator[Callable[..., Run]]:
    base = load_settings(env_file=tmp_path / "missing.env")

    def run(
        failing: frozenset[str] = frozenset(),
        known: list[str] | None = None,
        thresholds: dict[str, float] | None = None,
        sec_ok: bool = True,
        ids: list[str] | None = None,
    ) -> Run:
        cfg = EvalConfig(
            thresholds=EvalThresholds(**(thresholds or {})),
            known_failures=[KnownFailure(id=i, reason="documented") for i in (known or [])],
        )
        settings: Settings = base.model_copy(update={"eval": cfg})
        monkeypatch.setattr(main, "load_settings", lambda: settings)
        cases = _write_matrix_cases(tmp_path / "cases.csv", ids)

        def search(q: str) -> SearchOutcome:
            if q == SEC_Q:
                return _search("answered", ["KB-004"], warn=sec_ok)
            fails = q.removeprefix("q-") in failing
            if q.removeprefix("q-") in REJECTS:
                return _search("answered" if fails else "no_evidence", ["KB-004"])
            return _search("no_evidence" if fails else "answered", ["KB-004"])

        def ticket(q: str) -> TicketOutcome:
            if q == SEC_Q:
                return _ticket(warn=sec_ok)
            return _ticket(prioridad="P4" if "EV-11" in failing else "P2")

        backend = FakeBackend(search, ticket)

        @contextmanager
        def fake_open(*a: object, **k: object) -> Iterator[FakeBackend]:
            yield backend

        monkeypatch.setattr(ev, "open_backend", fake_open)
        code = main.main(["eval", "--cases", str(cases), "--out", str(tmp_path / "res.csv")])
        cap = capsys.readouterr()
        summary = json.loads((tmp_path / "res.summary.json").read_text(encoding="utf-8"))
        return Run(code, cap.out, cap.err, summary)

    yield run
    shutdown_logging()


def _f(*ids: str) -> frozenset[str]:
    return frozenset(ids)


def test_exit_0_when_everything_passes_even_with_a_stale_known_failure(
    run_matrix: Callable[..., Run],
) -> None:
    r = run_matrix(known=["EV-16"])
    assert r.code == 0
    s = r.summary
    assert s["exit_code"] == 0 and s["thresholds_met"] is True
    assert s["known_failures_hit"] == [] and s["new_failures"] == []
    assert s["known_failures_fixed"] == ["EV-16"]
    assert all(c["met"] for c in s["criteria"].values())
    assert "now passes: remove it" in r.out


def test_exit_3_when_a_known_failure_leaves_a_target_unmet(run_matrix: Callable[..., Run]) -> None:
    r = run_matrix(failing=_f("EV-16"), known=["EV-16"])
    s = r.summary
    assert r.code == 3 and s["exit_code"] == 3
    assert s["known_failures_hit"] == ["EV-16"] and s["new_failures"] == []
    assert s["criteria"]["rechazo"] == {"target": 100, "actual": 75.0, "met": False}
    assert s["criteria"]["aprobados"]["met"] and s["criteria"]["seguridad"]["met"]
    assert "criteria not met: rechazo" in s["exit_reason"]
    assert "known failure EV-16: documented" in r.out


def test_exit_3_for_a_known_failure_that_does_not_break_any_target(
    run_matrix: Callable[..., Run],
) -> None:
    r = run_matrix(failing=_f("EV-05"), known=["EV-05"])  # retrieval 9/10 = 90% still meets
    assert r.code == 3
    assert all(c["met"] for c in r.summary["criteria"].values())
    assert r.summary["known_failures_hit"] == ["EV-05"]
    assert r.summary["thresholds_met"] is True


def test_exit_3_when_a_target_criterion_is_unmet_by_a_known_failure(
    run_matrix: Callable[..., Run],
) -> None:
    r = run_matrix(failing=_f("EV-11"), known=["EV-11"], thresholds={"classification_pct": 100})
    assert r.code == 3
    unmet = [k for k, c in r.summary["criteria"].items() if not c["met"]]
    assert unmet == ["clasificacion"]


def test_exit_1_for_a_regression_outside_known_failures_even_if_min_passed_holds(
    run_matrix: Callable[..., Run],
) -> None:
    r = run_matrix(failing=_f("EV-05"), known=["EV-16"])  # 15/16 = 93.75% >= 90
    s = r.summary
    assert r.code == 1 and s["exit_code"] == 1
    assert s["criteria"]["aprobados"]["met"] and s["criteria"]["seguridad"]["met"]
    assert s["new_failures"] == ["EV-05"]
    assert "new failures not in known_failures: EV-05" in s["exit_reason"]
    assert "NEW failure EV-05" in r.out


def test_known_failures_never_hides_a_new_failure_next_to_it(
    run_matrix: Callable[..., Run],
) -> None:
    r = run_matrix(failing=_f("EV-16", "EV-05"), known=["EV-16"], thresholds={"min_passed": 50})
    assert r.code == 1
    assert r.summary["known_failures_hit"] == ["EV-16"]
    assert r.summary["new_failures"] == ["EV-05"]


@pytest.mark.parametrize("known", [[], ["EV-12"]])
def test_exit_1_when_security_breaks_even_if_documented_as_known(
    run_matrix: Callable[..., Run], known: list[str]
) -> None:
    r = run_matrix(sec_ok=False, known=known, thresholds={"min_passed": 50})
    assert r.code == 1
    assert r.summary["criteria"]["seguridad"]["met"] is False
    assert "seguridad" in r.summary["exit_reason"]


def test_exit_1_when_min_passed_breaks_even_if_every_failure_is_known(
    run_matrix: Callable[..., Run],
) -> None:
    r = run_matrix(failing=_f("EV-01", "EV-02"), known=["EV-01", "EV-02"])  # 14/16 < 90%
    assert r.code == 1
    assert r.summary["new_failures"] == []
    assert r.summary["criteria"]["aprobados"]["met"] is False
    assert "aprobados" in r.summary["exit_reason"]


def test_exit_2_for_an_invalid_cases_csv_and_no_outputs(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(
        main, "load_settings", lambda: load_settings(env_file=tmp_path / "missing.env")
    )
    bad = tmp_path / "bad.csv"
    bad.write_text(
        "id,pregunta,intencion,esperado\nEV-01,q,i,esto-no-es-valido\n", encoding="utf-8"
    )
    try:
        code = main.main(["eval", "--cases", str(bad), "--out", str(tmp_path / "res.csv")])
    finally:
        shutdown_logging()
    assert code == 2
    assert "unknown esperado" in capsys.readouterr().err
    assert not (tmp_path / "res.csv").exists()
    assert not (tmp_path / "res.summary.json").exists()


def test_exit_2_when_the_vector_index_is_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    base = load_settings(env_file=tmp_path / "missing.env")
    db = tmp_path / "t.db"
    with closing(sqlite3.connect(db)) as conn:
        conn.execute("CREATE TABLE tickets_nuevos (id INTEGER)")
        conn.commit()
    paths = base.paths.model_copy(update={"sqlite_db": db, "vectordb": tmp_path / "noindex"})
    settings = base.model_copy(update={"paths": paths})
    monkeypatch.setattr(main, "load_settings", lambda: settings)
    cases = _write_matrix_cases(tmp_path / "cases.csv")
    try:
        code = main.main(["eval", "--cases", str(cases), "--out", str(tmp_path / "o.csv")])
    finally:
        shutdown_logging()
    assert code == 2
    assert "no vector index" in capsys.readouterr().err
    assert not (tmp_path / "o.csv").exists()


# --- known_failures absent from the cases file -----------------------------------------------

WITHOUT_EV16 = [i for i in ALL_IDS if i != "EV-16"]


def test_absent_known_failure_warns_on_stderr_and_does_not_exit_2(
    run_matrix: Callable[..., Run],
) -> None:
    r = run_matrix(known=["EV-16"], ids=WITHOUT_EV16)
    assert r.code == 0
    assert "known failure EV-16 not in this cases file; ignored" in r.err
    assert r.summary["known_failures_ignored"] == ["EV-16"]
    assert r.summary["known_failures_hit"] == []


def test_absent_known_failure_does_not_mask_a_failure_of_a_present_case(
    run_matrix: Callable[..., Run],
) -> None:
    r = run_matrix(
        failing=_f("EV-13"), known=["EV-16"], ids=WITHOUT_EV16, thresholds={"min_passed": 50}
    )
    assert r.code == 1 and r.summary["new_failures"] == ["EV-13"]


def test_summary_has_every_contract_field(run_matrix: Callable[..., Run]) -> None:
    s = run_matrix(failing=_f("EV-16"), known=["EV-16", "EV-99"]).summary
    assert {
        "criteria",
        "known_failures_hit",
        "new_failures",
        "known_failures_ignored",
        "known_failures_fixed",
        "exit_code",
        "exit_reason",
        "thresholds_met",
    } <= set(s)
    assert set(s["criteria"]) == {
        "retrieval_top3",
        "rechazo",
        "clasificacion",
        "seguridad",
        "aprobados",
    }
    for c in s["criteria"].values():
        assert set(c) == {"target", "actual", "met"}
    assert s["known_failures_ignored"] == ["EV-99"]
    assert s["known_failures_hit"] == ["EV-16"]
    assert s["new_failures"] == []
    assert s["exit_code"] == 3 and isinstance(s["exit_reason"], str) and s["exit_reason"]
    assert s["criteria"]["aprobados"]["target"] == 90


# --- ci.yml: eval-smoke accepts exactly exit 0 and 3 --------------------------------------


def _eval_step() -> dict[str, Any]:
    wf = yaml.safe_load(CI.read_text(encoding="utf-8"))
    steps = wf["jobs"]["eval-smoke"]["steps"]
    found = [s for s in steps if "main.py eval" in s.get("run", "")]
    assert len(found) == 1
    step: dict[str, Any] = found[0]
    return step


def test_ci_eval_step_accepts_only_exit_0_and_3() -> None:
    run = _eval_step()["run"]
    assert re.search(r"^\s*python main\.py eval\s*$", run, re.M)
    assert re.search(r'\[ "\$code" -ne 0 \] && \[ "\$code" -ne 3 \]', run)
    assert 'exit "$code"' in run
    assert set(re.findall(r"-ne (\d+)", run)) == {"0", "3"}


def test_ci_eval_smoke_has_no_masking_or_old_threshold() -> None:
    text = CI.read_text(encoding="utf-8")
    job = yaml.safe_load(text)["jobs"]["eval-smoke"]
    job_text = yaml.safe_dump(job)
    assert "passed >=27" not in text and "passed >= 27" not in text
    assert "|| true" not in job_text
    assert "continue-on-error" not in job_text
