"""Tests for the VALIDATION/MSBADGES blocks and the honesty contract of the docs (anti-oversell)."""

from __future__ import annotations

import copy
import json
import re
from pathlib import Path
from typing import Any

import pytest

from scripts import update_readme_results as urr

ROOT = Path(__file__).resolve().parents[2]
IDS = ("fabric", "copilot_studio", "power_bi", "video")
PENDING_TEXT = "⏳ Pending validation on a real tenant"  # script wording (English since bda3acf)
GREEN = "2EA043"
SUMMARY: dict[str, Any] = {
    "generated_at": "2026-05-01T10:00:00+00:00",
    "backend": "local",
    "total": 10,
    "metrics": {
        "aprobados": {"passed": 9, "total": 10, "pct": 90.0, "threshold_pct": 90, "met": True},
    },
    "latency_ms": {"p50": 1.0, "p95": 2.0},
    "cases": {},
}


def _item(key: str) -> dict[str, Any]:
    return {
        "id": key,
        "nombre": f"Nombre {key}",
        "estado": "pendiente",
        "fecha": None,
        "evidencia": None,
        "que_falta": f"Falta {key}",
    }


def _all_pending() -> list[dict[str, Any]]:
    return [_item(k) for k in IDS]


def _validated(key: str, status: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out = copy.deepcopy(status)
    for item in out:
        if item["id"] == key:
            item.update(estado="validado", fecha="2026-12-01", evidencia="docs/evidence/x.md")
    return out


class Env:
    def __init__(self, tmp: Path) -> None:
        self.summary = tmp / "summary.json"
        self.readme = tmp / "README.md"
        self.doc = tmp / "testing.md"
        self.status = tmp / "status.json"
        self.summary.write_text(json.dumps(SUMMARY), encoding="utf-8")
        self.doc.write_text("# x\n", encoding="utf-8")
        self.write_status(_all_pending())

    def write_status(self, data: Any) -> None:
        self.status.write_text(json.dumps(data), encoding="utf-8")

    def write_readme(self, text: str, eol: str = "\n") -> None:
        self.readme.write_bytes(text.replace("\n", eol).encode("utf-8"))

    def run(self, *extra: str) -> int:
        return urr.main(
            [
                *("--summary", str(self.summary), "--readme", str(self.readme)),
                *("--testing-doc", str(self.doc), "--status", str(self.status), *extra),
            ]
        )

    def text(self) -> str:
        return self.readme.read_bytes().decode("utf-8")


FULL = (
    "# T\nantes\n<!-- RESULTS:START -->\nx\n<!-- RESULTS:END -->\n"
    "mid\n<!-- MSBADGES:START -->\nold\n<!-- MSBADGES:END -->\n"
    "<!-- VALIDATION:START -->\nold\n<!-- VALIDATION:END -->\nfin"
)


@pytest.fixture
def env(tmp_path: Path) -> Env:
    e = Env(tmp_path)
    e.write_readme(FULL)
    return e


# --- schema ---------------------------------------------------------------------------


def _mutate(fn: Any) -> list[dict[str, Any]]:
    data = _all_pending()
    fn(data)
    return data


SCHEMA_CASES = {
    "missing_id": (lambda d: d.pop(), "missing integrations"),
    "duplicate": (lambda d: d.__setitem__(3, _item("fabric")), "repeated"),
    "unknown_id": (lambda d: d[0].__setitem__("id", "excel"), "unknown id"),
    "extra_field": (lambda d: d[0].__setitem__("extra", 1), "exactly the fields"),
    "missing_field": (lambda d: d[0].pop("que_falta"), "exactly the fields"),
    "bad_estado": (lambda d: d[0].__setitem__("estado", "listo"), "estado"),
    "pending_with_fecha": (lambda d: d[0].__setitem__("fecha", "2026-01-01"), "pendiente"),
    "pending_with_evidencia": (lambda d: d[0].__setitem__("evidencia", "x.md"), "pendiente"),
    "not_a_list": (lambda d: None, "list"),
}


@pytest.mark.parametrize("case", SCHEMA_CASES)
def test_invalid_schema_exits_2_naming_the_problem(
    env: Env, case: str, capsys: pytest.CaptureFixture[str]
) -> None:
    mutate, expected = SCHEMA_CASES[case]
    data: Any = _mutate(mutate)
    if case == "not_a_list":
        data = {"fabric": "x"}
    env.write_status(data)
    before = env.text()
    assert env.run() == urr.EXIT_BAD_INPUT == 2
    assert expected in capsys.readouterr().out
    assert env.text() == before


@pytest.mark.parametrize(
    ("fecha", "evidencia"),
    [
        (None, "e.md"),
        ("2026-12-01", None),
        ("2026-12-01", "   "),
        ("", "e.md"),
        ("2026-13-45", "e.md"),
        ("01/12/2026", "e.md"),
        ("2026-12-01T10:00", "e.md"),
    ],
)
def test_validado_requires_valid_date_and_evidence(
    env: Env, fecha: Any, evidencia: Any, capsys: pytest.CaptureFixture[str]
) -> None:
    data = _all_pending()
    data[0].update(estado="validado", fecha=fecha, evidencia=evidencia)
    env.write_status(data)
    assert env.run() == 2
    assert "fabric" in capsys.readouterr().out


def test_invalid_json_and_missing_status_exit_2(env: Env) -> None:
    env.status.write_text("{no json", encoding="utf-8")
    assert env.run() == 2
    env.status.unlink()
    assert env.run() == 2


# --- rendering ------------------------------------------------------------------------


def test_all_pending_renders_pending_table_and_grey_badges(env: Env) -> None:
    assert env.run() == 0
    text = env.text()
    assert text.count(PENDING_TEXT) == 4
    assert "✅ Validated" not in text
    assert GREEN not in text and "brightgreen" not in text
    assert text.count("6B7280") == 2
    for key in IDS:
        assert f"Nombre {key}" in text and f"Falta {key}" in text


def test_one_validated_turns_only_its_badge_green(env: Env) -> None:
    env.write_status(_validated("fabric", _all_pending()))
    assert env.run() == 0
    text = env.text()
    badges = re.search(r"<!-- MSBADGES:START -->\n(.*?)\n<!-- MSBADGES:END -->", text, re.S)
    assert badges
    lines = [ln for ln in badges.group(1).splitlines() if ln]
    fabric = next(ln for ln in lines if "![Fabric" in ln)
    copilot = next(ln for ln in lines if "![Copilot" in ln)
    assert "Fabric" in fabric and GREEN in fabric and "validated on 2026-12-01" in fabric
    assert "Copilot%20Studio" in copilot and GREEN not in copilot and "6B7280" in copilot
    assert "✅ Validated (2026-12-01)" in text
    assert "docs/evidence/x.md" in text
    assert text.count(PENDING_TEXT) == 3


def test_validated_power_bi_or_video_never_greens_a_badge(env: Env) -> None:
    env.write_status(_validated("video", _validated("power_bi", _all_pending())))
    assert env.run() == 0
    assert GREEN not in env.text()
    assert env.text().count("✅ Validated (") == 2


def test_validated_without_evidence_cannot_be_forced_green(env: Env) -> None:
    """Anti-falseo: flipping the real JSON to validado with no evidence fails, writes nothing."""
    data = json.loads((ROOT / "docs" / "validation-status.json").read_text(encoding="utf-8"))
    data[1]["estado"] = "validado"
    env.write_status(data)
    before = env.text()
    assert env.run() == 2
    assert env.run("--check") == 2
    assert env.text() == before and GREEN not in before


# --- idempotence, modes, markers ------------------------------------------------------


def test_two_runs_are_byte_identical_and_check_flow(env: Env) -> None:
    assert env.run("--check") == 1
    assert env.run() == 0
    first = env.readme.read_bytes()
    assert env.run() == 0
    assert env.readme.read_bytes() == first
    assert env.run("--check") == 0
    env.write_status(_validated("copilot_studio", _all_pending()))
    assert env.run("--check") == 1
    assert env.readme.read_bytes() == first


def test_dry_run_does_not_write_and_shows_blocks(
    env: Env, capsys: pytest.CaptureFixture[str]
) -> None:
    before = env.readme.read_bytes()
    assert env.run("--dry-run") == 0
    out = capsys.readouterr().out
    assert PENDING_TEXT in out and "img.shields.io" in out
    assert env.readme.read_bytes() == before


@pytest.mark.parametrize(
    "bad",
    [
        FULL + "\n<!-- VALIDATION:START -->\n<!-- VALIDATION:END -->",
        FULL + "\n<!-- MSBADGES:END -->",
        FULL.replace("<!-- MSBADGES:START -->", "<!-- X -->"),
        FULL.replace("<!-- VALIDATION:END -->", "<!-- X -->"),
        "<!-- RESULTS:START -->\n<!-- RESULTS:END -->\n"
        "<!-- VALIDATION:END -->\n<!-- VALIDATION:START -->",
    ],
)
def test_duplicate_or_misordered_markers_exit_2(env: Env, bad: str) -> None:
    env.write_readme(bad)
    before = env.readme.read_bytes()
    assert env.run() == 2
    assert env.readme.read_bytes() == before


def test_without_status_markers_blocks_are_skipped_and_json_not_required(env: Env) -> None:
    env.write_readme("a\n<!-- RESULTS:START -->\nx\n<!-- RESULTS:END -->\nb")
    env.status.unlink()
    assert env.run() == 0
    assert "Pending validation" not in env.text()
    assert env.run("--check") == 0


def test_text_outside_markers_is_untouched(env: Env) -> None:
    assert env.run() == 0
    text = env.text()
    assert text.startswith("# T\nantes\n<!-- RESULTS:START -->\n")
    assert "\nmid\n<!-- MSBADGES:START -->\n" in text
    assert text.endswith("<!-- VALIDATION:END -->\nfin")


def test_crlf_is_preserved(env: Env) -> None:
    env.write_readme(FULL, "\r\n")
    assert env.run() == 0
    raw = env.readme.read_bytes()
    assert b"\n" not in raw.replace(b"\r\n", b"")
    assert PENDING_TEXT.encode() in raw
    assert env.run() == 0 and env.readme.read_bytes() == raw
    assert env.run("--check") == 0


# --- honesty contract on the real docs ------------------------------------------------


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def _status() -> dict[str, dict[str, Any]]:
    return {i["id"]: i for i in json.loads(_read("docs/validation-status.json"))}


def _group(readme: str, heading: str, until: str) -> str:
    start = readme.index(heading)
    return readme[start : readme.index(until, start + len(heading))]


def test_real_status_file_passes_the_schema() -> None:
    assert urr._status_problem(json.loads(_read("docs/validation-status.json"))) is None


def test_real_readme_is_up_to_date_with_status(capsys: pytest.CaptureFixture[str]) -> None:
    assert urr.main(["--check"]) == 0, capsys.readouterr().out


def test_real_readme_status_matches_json() -> None:
    readme = _read("README.md")
    table = re.search(r"<!-- VALIDATION:START -->(.*?)<!-- VALIDATION:END -->", readme, re.S)
    assert table
    for key, item in _status().items():
        row = next(ln for ln in table.group(1).splitlines() if item["nombre"] in ln)
        if item["estado"] == "validado":
            assert "✅ Validated" in row and item["fecha"] in row, key
        else:
            assert PENDING_TEXT in row and "✅" not in row, key


def test_real_badges_are_green_only_for_validated_integrations() -> None:
    readme = _read("README.md")
    badges = re.search(r"<!-- MSBADGES:START -->(.*?)<!-- MSBADGES:END -->", readme, re.S)
    assert badges
    status = _status()
    lines = badges.group(1).strip().splitlines()
    assert len(lines) == 2
    for line in lines:
        key = "copilot_studio" if "Copilot" in line else "fabric"
        green = GREEN in line or "brightgreen" in line
        assert green == (status[key]["estado"] == "validado"), line


def test_no_green_microsoft_badge_anywhere_in_readme_while_pending() -> None:
    status = _status()
    for line in _read("README.md").splitlines():
        if "img.shields.io/badge" in line and re.search(r"Copilot|Fabric|Power", line):
            key = "fabric" if "Fabric" in line else "copilot_studio"
            if status[key]["estado"] != "validado":
                assert not re.search(r"2EA043|brightgreen|success|green", line, re.I), line


def _skills_rows(readme: str) -> list[list[str]]:
    """Rows of the single 'Skills demonstrated' table (Skill | Evidence | Status)."""
    match = re.search(r"^## [^\n]*Skills demonstrated\s*$(.*?)(?=^## )", readme, re.S | re.M)
    assert match, "section 'Skills demonstrated' missing"
    lines = [ln for ln in match.group(1).splitlines() if ln.startswith("|")]
    rows = [[c.strip() for c in ln.strip().strip("|").split("|")] for ln in lines]
    assert rows[0] == ["Skill", "Evidence", "Status"], rows[0]
    return rows[2:]  # skip header and separator


def test_skills_table_has_status_column_and_ms_stack_is_not_done() -> None:
    """README v2 replaced the two skill groups by one table with a Status column.

    The honesty contract is unchanged: Fabric, Copilot Studio and Power BI rows must say
    'pending' and never 'Done' while status.json has them pending; other rows do say Done.
    """
    rows = _skills_rows(_read("README.md"))
    assert any(r[2].startswith("Done") for r in rows), "no row is marked Done"
    status = _status()
    for name, key in (
        ("Microsoft Fabric", "fabric"),
        ("Copilot Studio", "copilot_studio"),
        ("Power BI", "power_bi"),
    ):
        row = next((r for r in rows if r[0] == name), None)
        assert row, f"skills table has no '{name}' row"
        if status[key]["estado"] == "pendiente":
            assert "pending" in row[2].lower() and not row[2].startswith("Done"), row
    for r in rows:
        if re.search(r"Fabric|Copilot|Power BI", r[0]):
            assert not r[2].startswith("Done"), f"MS stack row marked Done: {r}"


CLAIM = re.compile(
    r"(validad[oa]s?|probad[oa]s?|verificad[oa]s?|ejecutad[oa]s?|desplegad[oa]s?)"
    r"[^.|\n]{0,25}(en (un |el )?tenant|contra (un |el )?tenant|en (microsoft )?fabric"
    r"|en copilot studio)",
    re.I,
)
NEGATION = re.compile(r"\b(no|ni|sin|pendiente|aún|todavía|hasta entonces|se validar)\b", re.I)
CLAIM_EN = re.compile(
    r"\b(validated|tested|verified|deployed|working|runs?)\b"
    r"[^.|\n]{0,25}(on (a |the )?(real )?tenant|against (a |the )?(real )?tenant"
    r"|in (microsoft )?fabric|in copilot studio)",
    re.I,
)
NEGATION_EN = re.compile(
    r"\b(not|no|never|pending|yet|without|designed|until|doubles|to be|isn't|aren't)\b", re.I
)


def _unnegated_claims(text: str) -> list[str]:
    hits = []
    for sentence in re.split(r"(?<=[.!?])\s+|\n", text):
        es = CLAIM.search(sentence) and not NEGATION.search(sentence)
        en = CLAIM_EN.search(sentence) and not NEGATION_EN.search(sentence)
        if es or en:
            hits.append(sentence.strip())
    return hits


def test_readme_never_claims_tenant_validation_outside_validated_status() -> None:
    readme = _read("README.md")
    outside = re.sub(r"<!-- VALIDATION:START -->.*?<!-- VALIDATION:END -->", "", readme, flags=re.S)
    if all(i["estado"] == "pendiente" for i in _status().values()):
        assert _unnegated_claims(outside) == []


PRESENT = [
    r"\b(se )?conecta(n)? (a|con) (microsoft )?fabric",
    r"\b(est[aá]|queda) desplegad[oa] en (microsoft )?(copilot studio|fabric)",
    r"\bdesplegado en copilot studio\b",
    r"\bfunciona (en|con) (microsoft )?(fabric|copilot studio)\b",
    r"\bel agente (responde|resuelve) en copilot studio\b",
    r"\b(consulta|lee|escribe) (el )?(lakehouse|warehouse) de fabric\b",
]


@pytest.mark.parametrize("doc", ["docs/job-fit.md", "docs/business-case.md", "README.md"])
def test_docs_do_not_assert_unvalidated_things_in_present_tense(doc: str) -> None:
    if any(i["estado"] == "validado" for i in _status().values()):
        pytest.skip("some integration is validated; wording is allowed to change")
    for line in _read(doc).splitlines():
        if NEGATION.search(line) or "prev" in line.lower() or "diseñ" in line.lower():
            continue
        for pattern in PRESENT:
            assert not re.search(pattern, line, re.I), f"{doc}: {line.strip()[:120]}"


def test_overselling_detector_flags_claims() -> None:
    assert _unnegated_claims("El agente está validado en tenant real.")
    assert _unnegated_claims("Fabric: probado en Microsoft Fabric.")
    assert _unnegated_claims("The agent is validated on a real tenant.")
    assert _unnegated_claims("Fabric: tested in Microsoft Fabric.")
    assert not _unnegated_claims("Fabric is designed but not yet validated on a real tenant.")
    assert not _unnegated_claims("Fabric no está validado en tenant real.")
    assert re.search(PRESENT[0], "El API se conecta a Fabric", re.I)


def test_job_fit_and_business_case_state_the_limit() -> None:
    assert "no están medidos" in _read("docs/job-fit.md")
    assert "no se han probado en un tenant real" in _read("docs/business-case.md")
