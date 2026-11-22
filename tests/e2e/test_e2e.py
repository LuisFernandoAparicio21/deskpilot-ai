"""End to end: generated data -> SQLite -> index -> API -> the 30 evaluation cases (T21, S12).

Everything lives in a temporary directory (the repo's database and index are never touched).
The default tests use the fake embedder for speed, so they only assert what does not depend
on embedding quality: RN-03 escalation by policy, RN-01 classification and RN-05 handling of
secrets. The ``slow`` tests run the 30 cases with the real fastembed model and check the
requirements section 12 thresholds; the failures found are strict xfails (see ``KNOWN_BUGS``).
"""

from __future__ import annotations

import csv
import hashlib
import json
import socket
import sqlite3
import threading
import time
from collections.abc import Iterator
from contextlib import closing, contextmanager
from pathlib import Path
from typing import Any

import pytest
import uvicorn
from pydantic import SecretStr

import main
from src.api import create_app
from src.api.evaluation import load_cases
from src.ingestion.sqlite_loader import load_sqlite
from src.ingestion.ticket_generator import generate_dataset
from src.utils.config import PROJECT_ROOT, Secrets, Settings, load_settings
from src.utils.logging import shutdown_logging
from src.vectordb.indexer import build_index

CASES = PROJECT_ROOT / "tests" / "eval" / "cases.csv"
API_KEY = "e2e-key-0123456789-abcdef"
SEED = 42
N_TICKETS = 400
SECRETS = ("Altiplano#2026", "4111 1111 1111 1111", "4111111111111111", "GOMA850101HDFRRL09")
RESULT_HEADER = "id,pregunta,intencion,esperado,obtenido,resultado,notas,latencia_ms"

# Cases that fail against the real index because the code contradicts a requirement.
KNOWN_BUGS: dict[str, str] = {
    "EV-05": "KB-011 in the evidence escalates a printer question (RN-03: cash only)",
    "EV-07": "KB-011 in the evidence escalates a core-banking access question (RN-03/RN-04)",
    "EV-09": "KB-011 in the evidence escalates a slow-computer question (RN-03/RN-04)",
    "EV-16": "KB-011 in the evidence escalates an out-of-KB question, not no_evidence (RF-05)",
    "EV-20": "RN-03/CT-06: unrecognized logins are not escalated as unauthorized access",
}


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _count_new_tickets(db: Path) -> int:
    with closing(sqlite3.connect(db)) as conn:
        return int(conn.execute("SELECT COUNT(*) FROM tickets_nuevos").fetchone()[0])


def _build_pipeline(tmp_path: Path, provider: str) -> Settings:
    """generate-data (seed 42) -> load-db -> index, all inside ``tmp_path``."""
    base = load_settings(env_file=tmp_path / "missing.env")
    paths = base.paths.model_copy(
        update={
            "raw": tmp_path / "raw",
            "sample": tmp_path / "sample",
            "logs": tmp_path / "logs",
            "vectordb": tmp_path / "vectordb",
            "sqlite_db": tmp_path / "deskpilot.db",
        }
    )
    settings = base.model_copy(
        update={
            "paths": paths,
            "embeddings": base.embeddings.model_copy(update={"provider": provider}),
            "secrets": Secrets(api_key=SecretStr(API_KEY)),
        }
    )
    generate_dataset(SEED, N_TICKETS, paths.raw, paths.sample, settings.sla_horas.model_dump())
    loaded = load_sqlite(paths.raw, paths.sqlite_db)
    assert loaded.n_tickets == N_TICKETS
    assert build_index(settings).n_articles == 15
    return settings


@pytest.fixture(scope="module")
def fake_settings(tmp_path_factory: pytest.TempPathFactory) -> Iterator[Settings]:
    yield _build_pipeline(tmp_path_factory.mktemp("e2e-fake"), "fake")
    shutdown_logging()


@pytest.fixture(scope="module")
def real_settings(tmp_path_factory: pytest.TempPathFactory) -> Iterator[Settings]:
    yield _build_pipeline(tmp_path_factory.mktemp("e2e-real"), "fastembed")
    shutdown_logging()


@contextmanager
def _serve(settings: Settings) -> Iterator[str]:
    """Run the real API with uvicorn in a thread; yields its base URL."""
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = int(sock.getsockname()[1])
    config = uvicorn.Config(
        create_app(settings), host="127.0.0.1", port=port, log_config=None, access_log=False
    )
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    deadline = time.monotonic() + 30
    while not server.started:
        if not thread.is_alive() or time.monotonic() > deadline:
            raise RuntimeError("the API did not start")
        time.sleep(0.05)
    try:
        yield f"http://127.0.0.1:{port}"
    finally:
        server.should_exit = True
        thread.join(timeout=15)


def _run_eval(
    settings: Settings, monkeypatch: pytest.MonkeyPatch, out: Path, *extra: str
) -> tuple[int, dict[str, Any]]:
    monkeypatch.setattr(main, "load_settings", lambda: settings)
    code = main.main(["eval", "--cases", str(CASES), "--out", str(out), *extra])
    summary_path = out.with_name(out.stem + ".summary.json")
    summary: dict[str, Any] = (
        json.loads(summary_path.read_text(encoding="utf-8")) if summary_path.is_file() else {}
    )
    return code, summary


# --- fake embedder: what does not depend on the embedding quality -----------------------


def test_local_eval_runs_the_30_cases_and_leaves_the_repo_database_alone(
    fake_settings: Settings, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    db = fake_settings.paths.sqlite_db
    sha_before, new_before = _sha(db), _count_new_tickets(db)
    out = tmp_path / "results.csv"

    code, summary = _run_eval(fake_settings, monkeypatch, out)

    assert code in (0, 1)  # 2 would be a configuration or infrastructure error
    assert summary["backend"] == "local"
    assert summary["total"] == 30
    assert len(summary["cases"]) == 30
    text = out.read_text(encoding="utf-8-sig")
    assert text.splitlines()[0] == RESULT_HEADER
    with out.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert [r["id"] for r in rows] == [f"EV-{i:02d}" for i in range(1, 31)]
    assert all(r["obtenido"] and r["resultado"] in ("pasó", "falló") for r in rows)
    # The evaluation worked on a copy: the source database is byte-identical.
    assert _sha(db) == sha_before
    assert _count_new_tickets(db) == new_before


def test_local_eval_security_and_classification_meet_the_requirements(
    fake_settings: Settings, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _, summary = _run_eval(fake_settings, monkeypatch, tmp_path / "r.csv")
    metrics = summary["metrics"]
    assert metrics["seguridad"]["passed"] == metrics["seguridad"]["total"] == 3  # RN-05, HU-05
    assert metrics["clasificacion"]["met"], metrics["clasificacion"]  # >= 85% (RN-01)


def test_no_secret_reaches_results_summary_or_logs(
    fake_settings: Settings, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    out = tmp_path / "r.csv"
    _run_eval(fake_settings, monkeypatch, out)
    shutdown_logging()  # flush the log files
    texts = [
        out.read_text(encoding="utf-8-sig"),
        out.with_suffix(".summary.json").read_text("utf-8"),
    ]
    texts += [
        p.read_text(encoding="utf-8", errors="replace") for p in fake_settings.paths.logs.glob("*")
    ]
    for secret in SECRETS:
        assert all(secret not in text for text in texts), secret


@pytest.mark.parametrize(
    "case_id",
    [
        "EV-19",
        "EV-21",
        "EV-22",
        pytest.param(
            "EV-20",
            marks=pytest.mark.xfail(strict=True, reason=KNOWN_BUGS["EV-20"]),
        ),
    ],
)
def test_mandatory_escalation_cases_pass_by_policy(
    case_id: str,
    fake_settings: Settings,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """RN-03 is decided from the query text, so it does not depend on the embedder."""
    _, summary = _run_eval(fake_settings, monkeypatch, tmp_path / "r.csv")
    assert summary["cases"][case_id] == "pasó"


def test_http_eval_gives_the_same_verdicts_and_persists_tickets_in_the_server_db(
    fake_settings: Settings, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    db = fake_settings.paths.sqlite_db
    local_code, local = _run_eval(fake_settings, monkeypatch, tmp_path / "local.csv")
    created_before = _count_new_tickets(db)
    with _serve(fake_settings) as url:
        code, http = _run_eval(
            fake_settings,
            monkeypatch,
            tmp_path / "http.csv",
            "--api-url",
            url,
            "--api-key",
            API_KEY,
        )
    assert code in (0, 1)
    assert local_code in (0, 1)
    assert http["backend"] == "http"
    assert http["total"] == 30
    # Same code path behind both backends; article cases differ (HTTP exposes only the cited one).
    same = [c for c in local["cases"] if int(c[3:]) >= 15]  # all but the article cases
    assert {c: http["cases"][c] for c in same} == {c: local["cases"][c] for c in same}
    # 5 ticket cases + 3 security cases create one ticket each in the server database.
    assert _count_new_tickets(db) - created_before == 8
    with closing(sqlite3.connect(db)) as conn:
        stored = " ".join(
            r[0] or "" for r in conn.execute("SELECT descripcion FROM tickets_nuevos")
        )
    for secret in SECRETS:
        assert secret not in stored  # RN-05: never persisted


def test_http_eval_with_a_wrong_key_is_a_configuration_error(
    fake_settings: Settings,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    with _serve(fake_settings) as url:
        code, summary = _run_eval(
            fake_settings,
            monkeypatch,
            tmp_path / "r.csv",
            "--api-url",
            url,
            "--api-key",
            "wrong-key-0123456789",
        )
    assert code == 2
    assert summary == {}
    assert "wrong-key-0123456789" not in capsys.readouterr().err


def test_eval_without_an_index_is_a_configuration_error(
    fake_settings: Settings,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    empty = fake_settings.paths.model_copy(update={"vectordb": tmp_path / "no-index"})
    code, _ = _run_eval(
        fake_settings.model_copy(update={"paths": empty}), monkeypatch, tmp_path / "r.csv"
    )
    assert code == 2
    assert "no vector index" in capsys.readouterr().err


# --- real fastembed model: section 12 thresholds over the 30 cases -----------------------


@pytest.fixture(scope="module")
def real_summary(
    real_settings: Settings, tmp_path_factory: pytest.TempPathFactory
) -> Iterator[dict[str, Any]]:
    monkeypatch = pytest.MonkeyPatch()
    try:
        _, summary = _run_eval(real_settings, monkeypatch, tmp_path_factory.mktemp("res") / "r.csv")
    finally:
        monkeypatch.undo()
    yield summary


def _case_params() -> list[Any]:
    params: list[Any] = []
    for case in load_cases(CASES):
        marks = (
            [pytest.mark.xfail(strict=True, reason=KNOWN_BUGS[case.id])]
            if case.id in KNOWN_BUGS
            else []
        )
        params.append(pytest.param(case.id, id=case.id, marks=marks))
    return params


@pytest.mark.slow
@pytest.mark.parametrize("case_id", _case_params())
def test_real_index_each_case_passes(case_id: str, real_summary: dict[str, Any]) -> None:
    assert real_summary["cases"][case_id] == "pasó"


@pytest.mark.slow
def test_real_index_metrics_that_meet_section_12(real_summary: dict[str, Any]) -> None:
    metrics = real_summary["metrics"]
    assert metrics["clasificacion"]["met"], metrics["clasificacion"]  # >= 85%
    assert metrics["seguridad"]["met"], metrics["seguridad"]  # 100%
    assert real_summary["latency_ms"]["p95"] > 0


@pytest.mark.slow
@pytest.mark.xfail(strict=True, reason="; ".join(KNOWN_BUGS.values()))
def test_real_index_all_section_12_thresholds_met(real_summary: dict[str, Any]) -> None:
    assert real_summary["thresholds_met"], {
        name: (m["passed"], m["total"], m["threshold_pct"])
        for name, m in real_summary["metrics"].items()
    }
