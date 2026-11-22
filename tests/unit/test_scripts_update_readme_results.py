"""Behavior tests for scripts/update_readme_results.py (S18, T25)."""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

import pytest

from scripts import update_readme_results as urr

SUMMARY: dict[str, Any] = {
    "generated_at": "2026-05-01T10:00:00+00:00",
    "backend": "local",
    "total": 10,
    "passed": 9,
    "metrics": {
        "aprobados": {"passed": 9, "total": 10, "pct": 90.0, "threshold_pct": 90, "met": True},
        "retrieval_top3": {"passed": 4, "total": 5, "pct": 80.0, "threshold_pct": 90, "met": False},
    },
    "latency_ms": {"p50": 12.5, "p95": 40.1},
    "cases": {"EV-01": "pasó", "EV-02": "falló", "EV-03": "pasó"},
}
PREFIX = "# Título ñ\r\nTexto previo con tabs\t y espacios al final   \r\n\r\n"
SUFFIX = "\r\n## Después\r\nfin sin salto"
TESTING_DOC = """# Procedimiento

## Otra sección

| ID | Pasó (sí/no) |
| --- | --- |
| EV-99 | sí |

## Resultados en Copilot Studio (T32)

Texto.

| ID | Pregunta | Esperado | Obtenido | Pasó (sí/no) | Notas |
| --- | --- | --- | --- | --- | --- |
| EV-01 | q | e | r | sí | |
| EV-02 | q | e | r | Si | |
| EV-03 | q | e | r | no | |
| EV-04 | q | e | r | PENDIENTE | |
| EV-05 | q | e | r | | |

## Siguiente

| ID | Pasó (sí/no) |
| --- | --- |
| EV-77 | sí |
"""


def _readme(eol: str = "\n", inner: str = "viejo") -> str:
    body = f"{urr.START}{eol}{inner}{eol}{urr.END}"
    return (PREFIX.replace("\r\n", eol)) + body + SUFFIX.replace("\r\n", eol)


class Env:
    def __init__(self, tmp: Path) -> None:
        self.summary = tmp / "summary.json"
        self.readme = tmp / "README.md"
        self.doc = tmp / "testing.md"
        self.write_summary(SUMMARY)
        self.doc.write_text(TESTING_DOC, encoding="utf-8")

    def write_summary(self, data: Any) -> None:
        self.summary.write_text(json.dumps(data), encoding="utf-8")

    def write_readme(self, text: str) -> None:
        self.readme.write_bytes(text.encode("utf-8"))

    def args(self, *extra: str) -> list[str]:
        return [
            "--summary", str(self.summary), "--readme", str(self.readme),
            "--testing-doc", str(self.doc), *extra,
        ]  # fmt: skip

    def run(self, *extra: str) -> int:
        return urr.main(self.args(*extra))

    def bytes(self) -> bytes:
        return self.readme.read_bytes()


@pytest.fixture
def env(tmp_path: Path) -> Env:
    return Env(tmp_path)


def test_update_is_idempotent(env: Env, capsys: pytest.CaptureFixture[str]) -> None:
    env.write_readme(_readme())
    assert env.run() == 0
    first = env.bytes()
    assert first != _readme().encode()
    assert "updated" in capsys.readouterr().out
    assert env.run() == 0
    assert env.bytes() == first
    assert "up to date" in capsys.readouterr().out


def test_check_exit_1_when_outdated_then_0_after_update(env: Env) -> None:
    env.write_readme(_readme())
    original = env.bytes()
    assert env.run("--check") == urr.EXIT_OUTDATED == 1
    assert env.bytes() == original  # --check never writes
    assert env.run() == 0
    assert env.run("--check") == 0


def test_dry_run_prints_block_and_writes_nothing(
    env: Env, capsys: pytest.CaptureFixture[str]
) -> None:
    env.write_readme(_readme())
    original = env.bytes()
    assert env.run("--dry-run") == 0
    out = capsys.readouterr().out
    assert "Cases passed" in out and "README would change" in out
    assert env.bytes() == original
    env.run()
    assert env.run("--dry-run") == 0
    assert "no changes" in capsys.readouterr().out.split("README would change")[-1]


def test_check_and_dry_run_are_mutually_exclusive(env: Env) -> None:
    with pytest.raises(SystemExit) as info:
        env.run("--check", "--dry-run")
    assert info.value.code == 2


def test_crlf_is_preserved_and_idempotent(env: Env) -> None:
    env.write_readme(_readme("\r\n"))
    assert env.run() == 0
    data = env.bytes()
    assert data.count(b"\n") == data.count(b"\r\n")  # no bare LF anywhere
    assert env.run() == 0
    assert env.bytes() == data
    assert env.run("--check") == 0


def test_lf_file_stays_lf(env: Env) -> None:
    env.write_readme(_readme("\n"))
    assert env.run() == 0
    assert b"\r" not in env.bytes()


def test_content_outside_markers_is_untouched_byte_for_byte(env: Env) -> None:
    env.write_readme(_readme("\r\n"))
    before = env.bytes()
    assert env.run() == 0
    after = env.bytes()
    start_end = urr.START.encode() + b"\r\n"
    assert after.startswith(PREFIX.encode() + start_end)
    assert after.endswith(urr.END.encode() + SUFFIX.encode())
    assert before.split(start_end)[0] == after.split(start_end)[0]
    assert not after.endswith(b"\n")  # the original had no final newline; it must not gain one


@pytest.mark.parametrize(
    "text",
    [
        "# sin marcadores\n",
        f"{urr.START}\nsolo inicio\n",
        f"solo fin\n{urr.END}\n",
        f"{urr.END}\nal revés\n{urr.START}\n",
        f"{urr.START}\na\n{urr.END}\n{urr.START}\nb\n{urr.END}\n",
    ],
    ids=["none", "only-start", "only-end", "reversed", "duplicate-pair"],
)
def test_bad_markers_exit_2_and_leave_readme_intact(
    env: Env, capsys: pytest.CaptureFixture[str], text: str
) -> None:
    env.write_readme(text)
    assert env.run() == urr.EXIT_BAD_INPUT == 2
    assert env.bytes() == text.encode()
    out = capsys.readouterr().out
    assert "exactly one" in out and "Traceback" not in out


def test_duplicate_end_marker_exit_2(env: Env) -> None:
    text = f"{urr.START}\na\n{urr.END}\nmedio\n{urr.END}\n"
    env.write_readme(text)
    assert env.run() == 2
    assert env.bytes() == text.encode()


@pytest.mark.parametrize(
    "text",
    [
        f"antes\n{urr.START}\nsin cierre\nfin\n",
        f"{urr.START}\n{urr.START}\n{urr.END}\n",
        f"antes\n{urr.END}\nmedio\n{urr.START}\nfin\n",
        f"{urr.END}{urr.START}",
    ],
    ids=["start-without-end", "two-starts-one-end", "end-before-start", "end-right-before-start"],
)
def test_unpaired_or_misordered_markers_exit_2_and_do_not_write(
    env: Env, capsys: pytest.CaptureFixture[str], text: str
) -> None:
    env.write_readme(text)
    assert env.run() == 2
    assert env.bytes() == text.encode()
    assert env.run("--check") == 2
    assert env.run("--dry-run") == 2
    out = capsys.readouterr().out
    assert "exactly one" in out and "Traceback" not in out


def test_missing_readme_exit_2(env: Env) -> None:
    assert env.run() == 2


@pytest.mark.parametrize(
    "content",
    ["{not json", "[1, 2]", '"text"', "{}", '{"metrics": {}, "latency_ms": {}}'],
    ids=["invalid-json", "list", "string", "empty-object", "missing-total"],
)
def test_invalid_summary_exit_2(env: Env, capsys: pytest.CaptureFixture[str], content: str) -> None:
    env.write_readme(_readme())
    original = env.bytes()
    env.summary.write_text(content, encoding="utf-8")
    assert env.run() == 2
    assert env.bytes() == original
    out = capsys.readouterr().out
    assert "main.py eval" in out and "Traceback" not in out


def test_missing_summary_exit_2(env: Env) -> None:
    env.write_readme(_readme())
    env.summary.unlink()
    assert env.run() == 2


@pytest.mark.parametrize(
    "mutate",
    [
        lambda s: s["metrics"]["aprobados"].pop("met"),
        lambda s: s["metrics"].__setitem__("aprobados", {}),
        lambda s: s.__setitem__("latency_ms", {}),
        lambda s: s.__setitem__("metrics", []),
    ],
    ids=["metric-lacks-met", "metric-empty", "latency-empty", "metrics-not-dict"],
)
def test_malformed_summary_contents_exit_2_not_a_traceback(env: Env, mutate: Any) -> None:
    """Valid top-level keys but broken inner values must still be 'bad input' (exit 2)."""
    data = copy.deepcopy(SUMMARY)
    mutate(data)
    env.write_summary(data)
    env.write_readme(_readme())
    assert env.run() == 2


def test_unknown_generated_at_renders_placeholder(env: Env) -> None:
    data = copy.deepcopy(SUMMARY)
    data["generated_at"] = "ayer"
    block = urr.render_block(data, None)
    assert "unknown date" in block


# --- T32 table -------------------------------------------------------------------------


def test_t32_table_counts_only_answered_rows_of_its_own_section(env: Env) -> None:
    assert urr.read_copilot_results(env.doc) == (2, 3)  # sí, Si pass; no fails; rest ignored
    env.write_readme(_readme())
    assert env.run() == 0
    assert "2 of 3 answered cases" in env.readme.read_text(encoding="utf-8")


def test_t32_all_pending_or_missing_means_pending(env: Env, tmp_path: Path) -> None:
    env.doc.write_text(TESTING_DOC.replace("| sí |", "| PENDIENTE |").replace("| no |", "| |")
                       .replace("| Si |", "| PENDIENTE |"), encoding="utf-8")  # fmt: skip
    assert urr.read_copilot_results(env.doc) is None
    assert urr.read_copilot_results(tmp_path / "nope.md") is None
    env.doc.write_text("# sin sección\n", encoding="utf-8")
    assert urr.read_copilot_results(env.doc) is None
    env.write_readme(_readme())
    assert env.run() == 0
    assert "pending (manual)" in env.readme.read_text(encoding="utf-8")


def test_t32_results_change_the_block(env: Env) -> None:
    env.write_readme(_readme())
    env.run()
    with_results = env.bytes()
    env.doc.write_text(TESTING_DOC.replace("| no |", "| sí |"), encoding="utf-8")
    assert env.run("--check") == 1
    env.run()
    assert env.bytes() != with_results
    assert "3 of 3 answered cases" in env.readme.read_text(encoding="utf-8")


# --- Metrics written == summary ---------------------------------------------------------


def _assert_block_matches(summary: dict[str, Any], block: str) -> None:
    for key, label in urr.METRIC_LABELS.items():
        metric = summary["metrics"].get(key)
        if metric is None:
            assert label not in block
            continue
        met = "yes" if metric["met"] else "no"
        row = (
            f"| {label} | {metric['passed']}/{metric['total']} ({metric['pct']}%) | "
            f">= {metric['threshold_pct']}% | {met} |"
        )
        assert row in block.splitlines()
    latency = summary["latency_ms"]
    assert f"p50 {latency['p50']} ms, p95 {latency['p95']} ms" in block
    failed = sorted(k for k, v in summary["cases"].items() if v != "pasó")
    expected = ", ".join(failed) if failed else "none"
    assert f"Failed cases: {expected}." in block
    assert f"Local evaluation of {summary['total']} cases" in block


def test_synthetic_summary_values_are_written(env: Env) -> None:
    env.write_readme(_readme())
    env.run()
    block = env.readme.read_text(encoding="utf-8")
    _assert_block_matches(SUMMARY, block)
    assert "Failed cases: EV-02." in block
    assert "Top-3 retrieval | 4/5 (80.0%) | >= 90% | no" in block
    assert "Ticket classification" not in block  # metric absent in the summary is skipped


def test_real_summary_metrics_match_the_written_block(env: Env) -> None:
    real = json.loads(urr.SUMMARY_PATH.read_text(encoding="utf-8"))
    env.summary.write_text(urr.SUMMARY_PATH.read_text(encoding="utf-8"), encoding="utf-8")
    env.write_readme(_readme())
    assert env.run() == 0
    block = env.readme.read_text(encoding="utf-8")
    _assert_block_matches(real, block)
    assert f"{real['passed']}/{real['total']}" in block  # aprobados


# --- The versioned README -------------------------------------------------------------


def test_versioned_readme_is_up_to_date(capsys: pytest.CaptureFixture[str]) -> None:
    """If this fails run `python -m scripts.update_readme_results` and commit README.md."""
    assert urr.main(["--check"]) == 0, capsys.readouterr().out
