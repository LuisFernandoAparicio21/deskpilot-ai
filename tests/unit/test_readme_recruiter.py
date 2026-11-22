"""Objective README checks taken from the recruiter research (no network, no pytest run).

Criteria are numbered as in ``docs/research/readme-for-recruiters.md`` ("CRITERIOS
VERIFICABLES", C1 to C20). Only what can be checked mechanically is checked here; opinion-only
criteria (tone, narrative) are not. Language is not a research criterion (P7 found no source):
it is a user decision recorded in ``docs/features/readme-redesign.md`` (single English README,
Spanish only in the two ``<sub>`` notes, the closing "Resumen en español" and agent replies).
Docs are never edited here: a mismatch fails with "doc vs real".
"""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path
from typing import Any

import pytest

import main
from scripts import update_readme_results as urr
from src.utils.config import PROJECT_ROOT

README = PROJECT_ROOT / "README.md"
SUMMARY = PROJECT_ROOT / "tests" / "eval" / "results.summary.json"
STATUS = PROJECT_ROOT / "docs" / "validation-status.json"
PROCEDURE = PROJECT_ROOT / "docs" / "testing-procedure.md"
BUSINESS_CASE = PROJECT_ROOT / "docs" / "business-case.md"
FENCE = "`" * 3

INTRO = (
    "DeskPilot AI is a level-1 IT service desk assistant for a fictional bank. "
    'It answers with cited knowledge-base articles and says "I don\'t know" when there is no '
    "evidence. It escalates fraud and unauthorized access, and exposes one service layer as a "
    "REST API and an MCP server. Local mode needs no paid keys; Fabric and Copilot Studio are "
    "designed but not yet validated on a real tenant."
)
SYNTHETIC_EN = "Synthetic data generated for this project; figures are illustrative."
SYNTHETIC_ES = "Datos sintéticos generados para este proyecto; las cifras son ilustrativas."
FICTIONAL_EN = "Banco Altiplano is a fictional bank. No real data from any bank or company is used."
FICTIONAL_ES = (
    "Banco Altiplano es un banco inventado. "
    "No se usan datos reales de ningún banco ni de ninguna empresa."
)
SPANISH_SECTION = "Resumen en español"


def _text() -> str:
    return README.read_text(encoding="utf-8")


def _strip_fences(text: str) -> str:
    """Drop fenced code blocks (``` ... ```), where ``#`` lines are shell comments."""
    return re.sub(
        r"^ {0,3}" + FENCE + r".*?^ {0,3}" + FENCE + r"[^\n]*$", "", text, flags=re.S | re.M
    )


def _unquote(text: str) -> str:
    """Remove blockquote markers so a quoted note reads as plain consecutive lines."""
    return re.sub(r"^>\s?", "", text, flags=re.M)


def _headings() -> list[tuple[int, str]]:
    body = _strip_fences(_text())
    return [
        (len(m.group(1)), m.group(2).strip())
        for m in re.finditer(r"^(#{1,6})\s+(.+?)\s*$", body, re.M)
    ]


def _section(heading: str) -> str:
    """Body of the H2 whose title ends with ``heading`` (emoji prefix allowed)."""
    body = _text()
    match = re.search(
        rf"^##\s+(?:\W+\s+)?{re.escape(heading)}\s*$(.*?)(?=^## |\Z)", body, re.S | re.M
    )
    assert match, f"section '## {heading}' missing"
    return match.group(1)


def _fenced_blocks(text: str, lang: str | None = None) -> list[str]:
    blocks = re.findall(r"^" + FENCE + r"(\w*)\n(.*?)^" + FENCE, text, re.S | re.M)
    return [body for tag, body in blocks if lang is None or tag == lang]


# C10: size and hierarchical headings ---------------------------------------------------


def test_c10_readme_is_under_500_kib() -> None:
    """C10 [GitHub Docs]: GitHub truncates a README above 500 KiB."""
    size = README.stat().st_size
    assert size < 500 * 1024, f"README is {size} bytes, limit {500 * 1024}"


def test_c10_single_h1_and_no_skipped_heading_levels() -> None:
    """C10 [GitHub Docs]: hierarchical headings feed the automatic table of contents."""
    headings = _headings()
    levels = [lvl for lvl, _ in headings]
    assert levels.count(1) == 1, f"expected one H1, found {levels.count(1)}"
    assert levels[0] == 1, "the first heading must be the H1"
    for (prev, _), (cur, title) in zip(headings, headings[1:], strict=False):
        assert cur <= prev + 1, f"heading level jumps from H{prev} to H{cur}: {title!r}"


# C20: scannable ------------------------------------------------------------------------


def test_c20_readme_is_scannable_tables_and_short_h2_sections() -> None:
    """C20 [Ladders, extrapolated]: clear headings, tables or short lists, simple hierarchy."""
    body = _strip_fences(_text())
    assert len(re.findall(r"^\|.*\|\s*$", body, re.M)) >= 20, "too few table rows"
    assert len([h for h in _headings() if h[0] == 2]) >= 8, "too few H2 sections"


# Language (user decision, not a research criterion) -------------------------------------

ES_WORDS = {
    "el", "la", "los", "las", "del", "que", "una", "para", "con", "por", "es", "se", "lo",
    "al", "como", "más", "pero", "sus", "está", "están", "hay", "sobre", "desde", "también",
    "muy", "este", "esta", "estos", "casos", "datos", "resumen",
}  # fmt: skip
EN_WORDS = {
    "the", "of", "and", "to", "in", "is", "for", "with", "on", "are", "that", "it", "as", "by",
    "not", "from", "this", "be", "or", "an", "at", "when", "no",
}  # fmt: skip


def _english_zone() -> str:
    """README text that must be English.

    Allowed Spanish zones are removed first: the two ``<sub>`` notes, the closing
    "Resumen en español" section and agent replies/examples (fenced blocks). Inline code
    (tool names such as ``buscar_solucion``), HTML comments and link targets are not prose.
    """
    text = re.sub(r"<!--.*?-->", "", _text(), flags=re.S)
    section = re.search(rf"^##\s+(?:\W+\s+)?{SPANISH_SECTION}\s*$.*", text, re.S | re.M)
    assert section, f"'{SPANISH_SECTION}' section missing"
    text = text[: section.start()]
    text = _strip_fences(text)
    text = re.sub(r"<sub>.*?</sub>", "", text, flags=re.S)
    text = re.sub(r"`[^`\n]*`", "", text)
    text = re.sub(r"\]\([^)]*\)", "]", text)
    text = re.sub(r'(?:src|srcset|href|alt|media)="[^"]*"', "", text)
    return text


def _words(line: str) -> list[str]:
    return re.findall(r"[a-záéíóúüñ]+", line.lower())


def test_language_prose_is_english_by_stopword_heuristic() -> None:
    """Heuristic: no line of the English zone may lean Spanish (more ES than EN stopwords),
    and the zone overall must carry many more EN than ES stopwords."""
    zone = _english_zone()
    es_total = en_total = 0
    for line in zone.splitlines():
        words = _words(line)
        es = sum(w in ES_WORDS for w in words)
        en = sum(w in EN_WORDS for w in words)
        es_total += es
        en_total += en
        assert not (es >= 2 and es >= en), f"line reads as Spanish: {line.strip()[:120]!r}"
    assert en_total > 100 and es_total * 20 < en_total, f"EN {en_total} vs ES {es_total}"


def test_language_h2_headings_are_english_except_the_spanish_summary() -> None:
    h2 = [title for lvl, title in _headings() if lvl == 2]
    assert any(SPANISH_SECTION in t for t in h2)
    for title in h2:
        if SPANISH_SECTION in title:
            continue
        words = _words(title)
        assert not [w for w in words if w in ES_WORDS], f"Spanish H2: {title!r}"
        assert not re.search(r"[áéíóúñ¿¡]", title.lower()), f"accented H2: {title!r}"
        assert len(words) >= 1


def test_language_spanish_appears_only_in_allowed_zones() -> None:
    """Accented/Spanish prose outside the allowed zones (including headings) is a leak."""
    zone = _english_zone()
    leaks = [ln.strip() for ln in zone.splitlines() if re.search(r"[áéíóúñ¿¡]", ln)]
    assert not leaks, f"Spanish characters in the English zone: {leaks[:3]}"
    assert len(re.findall(r"<sub>", _text())) == 2, "exactly two <sub> notes expected"


def test_language_one_line_says_tools_and_agent_replies_may_be_spanish() -> None:
    """Honest labeling: the English README shows Spanish tool names and agent replies."""
    match = [
        ln
        for ln in _text().splitlines()
        if re.search(r"tool names", ln, re.I) and re.search(r"agent repl", ln, re.I)
    ]
    assert match, "no line explains that tool names / agent replies stay in Spanish"
    assert "Spanish" in match[0]


# The three exact textual blocks ----------------------------------------------------------


def test_block_a_intro_paragraph_is_exact_and_has_no_english_label() -> None:
    text = _text()
    assert f"\n\n{INTRO}\n\n" in text, "intro paragraph differs from the agreed text"
    assert not re.search(r"(?m)^\W*English:", text), "label 'English:' must not appear"
    assert text.index(INTRO) < text.index("## ", text.index("# DeskPilot AI")), (
        "intro must come before the first H2"
    )


def test_block_b_synthetic_data_note_is_exact_with_spanish_sub_below() -> None:
    quoted = _unquote(_text())
    assert re.search(
        re.escape(SYNTHETIC_EN).join((r"\*{0,2}", r"\*{0,2}\n<sub>"))
        + re.escape(SYNTHETIC_ES)
        + r"</sub>",
        quoted,
    ), "synthetic-data note (EN) must be followed by the exact Spanish <sub>"


def test_block_c_fictional_bank_note_is_exact_with_spanish_sub_below() -> None:
    quoted = _unquote(_text())
    assert re.search(
        re.escape(FICTIONAL_EN).join((r"\*{0,2}", r"\*{0,2}\n<sub>"))
        + re.escape(FICTIONAL_ES)
        + r"</sub>",
        quoted,
    ), "Banco Altiplano note (EN) must be followed by the exact Spanish <sub>"


def test_spanish_summary_is_last_h2_with_three_or_four_lines() -> None:
    h2 = [title for lvl, title in _headings() if lvl == 2]
    assert SPANISH_SECTION in h2[-1], f"last H2 is {h2[-1]!r}"
    lines = [ln for ln in _section(SPANISH_SECTION).splitlines() if ln.strip()]
    assert 3 <= len(lines) <= 4, f"Spanish summary has {len(lines)} lines"
    assert "sintéticos" in " ".join(lines)


def test_no_readme_variant_files_in_the_repo() -> None:
    """Single README (user decision): no README.es.md / README.en.md / README-*.md copies.

    Module docs named exactly ``README.md`` in subfolders (src/*, docs/adr, integrations) are
    ordinary documentation, not translations of the top README.
    """
    tracked = subprocess.run(
        ["git", "ls-files"], cwd=PROJECT_ROOT, capture_output=True, text=True, check=True
    ).stdout.splitlines()
    variants = [
        f
        for f in tracked
        if re.fullmatch(r"README[._-].+\.(md|markdown|rst|txt)", Path(f).name)
        or (("/" not in f) and f.lower().startswith("readme") and f != "README.md")
    ]
    assert not variants, f"README variants tracked: {variants}"
    assert "README.md" in tracked
    on_disk = [p.name for p in PROJECT_ROOT.glob("README*") if p.name != "README.md"]
    assert not on_disk, f"README variants on disk: {on_disk}"


# C1, C2, C3, C14: what, how, example, limits ----------------------------------------------


def test_c1_readme_opens_with_what_it_does_and_why() -> None:
    """C1 [GitHub Docs, Google]: first lines say what the project does and why it is useful."""
    head = "\n".join(_text().splitlines()[:30])
    assert INTRO in head, "the 'what it does' paragraph must be in the first 30 lines"
    why = _section("Why this project")
    assert len(why.split()) > 40


def test_c2_quickstart_commands_exist_in_main_help() -> None:
    """C2 [Microsoft Learn]: minimal start steps that match the real CLI (`main.py --help`)."""
    quick = _section("Quickstart")
    assert "Python 3.13" in quick, "requirements (Python version) not declared"
    commands = set(re.findall(r"python main\.py ([a-z][a-z-]*)", quick))
    assert {"generate-data", "load-db", "index", "serve"} <= commands
    help_text = main.build_parser().format_help()
    for name in sorted(commands):
        assert name in main.SUBCOMMANDS, f"unknown subcommand {name}"
        assert re.search(rf"^\s+{re.escape(name)}\s", help_text, re.M), f"{name} not in --help"
    for needed in ("requirements.txt", "requirements-dev.txt", ".env.example"):
        assert needed in quick and (PROJECT_ROOT / needed).is_file(), f"{needed} missing"


def test_c3_usage_example_has_expected_output() -> None:
    """C3 [Microsoft Learn, Google]: an example of use with the expected (real) output."""
    section = _section("Usage example")
    assert "curl" in section and "/buscar_solucion" in section
    outputs = [json.loads(b) for b in _fenced_blocks(section, "json")]
    assert outputs, "no JSON output block"
    first = outputs[0]
    assert first["status"] == "answered" and first["citations"], first
    assert {o["status"] for o in outputs if "status" in o} >= {"answered", "no_evidence"}


def test_c13_c14_status_and_limits_section_is_concise_and_before_quickstart() -> None:
    """C13/C14 [Make a README; idratherbewriting]: status and main limits, few bullets,
    near the top (the research asks for limits at the start, in a few lines)."""
    h2 = [title for lvl, title in _headings() if lvl == 2]
    idx = {
        name: i
        for i, t in enumerate(h2)
        for name in ("Status and limits", "Quickstart")
        if t.endswith(name)
    }
    assert idx["Status and limits"] < idx["Quickstart"]
    section = _section("Status and limits")
    bullets = re.findall(r"^- ", section, re.M)
    assert 2 <= len(bullets) <= 6, f"limits should be concise, found {len(bullets)} bullets"
    assert "**Status:**" in section
    assert "## " not in _section("Next steps") and _section("Next steps").strip(), "no roadmap"


def test_c5_c6_complex_steps_are_linked_to_docs_not_inlined() -> None:
    """C5/C6 [Microsoft Learn, Google]: Docker/Fabric/MCP guides and docs/ are linked."""
    quick = _section("Quickstart")
    for target in (
        "docs/features/docker.md",
        "docs/MANUAL_STEPS.md",
        "docs/features/mcp-server.md",
    ):
        assert f"]({target})" in quick, f"quickstart does not link {target}"
    assert "docker build" not in _text() and "docker run" not in _text()
    assert _text().count("](docs/") >= 15


def test_c7_c8_license_maintainer_and_contributing() -> None:
    """C7/C8 [Google, GitHub Docs, Microsoft Learn]: status, maintainer, license, how to help."""
    maintainer = _section("Maintainer and contributing")
    assert "@LuisFernandoAparicio21" in maintainer and "/issues" in maintainer
    for rel in ("CONTRIBUTING.md", "CHANGELOG.md"):
        assert f"]({rel})" in maintainer and (PROJECT_ROOT / rel).is_file()
    license_section = _section("License")
    assert "](LICENSE)" in license_section and (PROJECT_ROOT / "LICENSE").is_file()
    assert "MIT" in license_section and "MIT" in (PROJECT_ROOT / "LICENSE").read_text("utf-8")


def test_c16_env_example_exists_and_is_referenced() -> None:
    """C16 [Code Labs Academy]: `.env.example` present; real `.env` is ignored by git."""
    assert (PROJECT_ROOT / ".env.example").is_file()
    assert re.search(r"^\.env$", (PROJECT_ROOT / ".gitignore").read_text("utf-8"), re.M)


# C11, C12: details and mermaid ------------------------------------------------------------


def test_c11_details_close_and_have_summary() -> None:
    """C11 [GitHub Docs]: every <details> closes and starts with a <summary>."""
    body = _strip_fences(_text())
    opens = len(re.findall(r"<details\b", body))
    assert opens == len(re.findall(r"</details>", body)) >= 1
    for block in re.findall(r"<details\b[^>]*>(.*?)</details>", _text(), re.S):
        assert re.match(r"\s*<summary>.+?</summary>", block, re.S), block[:60]


def test_c12_every_mermaid_block_is_a_real_fenced_flowchart() -> None:
    """C12 [GitHub Docs]: diagrams use mermaid fences GitHub renders."""
    blocks = _fenced_blocks(_text(), "mermaid")
    assert len(blocks) >= 2
    assert all(re.match(r"\s*(flowchart|sequenceDiagram|graph)", b) for b in blocks)


# Links, images, markers ----------------------------------------------------------------------


def _relative_targets() -> list[str]:
    body = _strip_fences(re.sub(r"<!--.*?-->", "", _text(), flags=re.S))
    body = re.sub(r"`[^`\n]*`", "", body)
    found = re.findall(r"\]\(([^)\s]+)", body)
    found += re.findall(r'(?:href|src|srcset)="([^"]+)"', body)
    return [t for t in found if not re.match(r"^([a-zA-Z][a-zA-Z0-9+.-]*:|//|#)", t)]


def test_c9_relative_links_and_local_images_resolve() -> None:
    """C9 [Google]: nothing stale; every relative link or image exists in the repo."""
    targets = _relative_targets()
    assert len(targets) > 25
    missing = [t for t in targets if not (PROJECT_ROOT / t.partition("#")[0]).exists()]
    assert not missing, f"README links to missing paths: {missing}"


@pytest.mark.parametrize(
    "start,end",
    [
        ("RESULTS:START", "RESULTS:END"),
        ("VALIDATION:START", "VALIDATION:END"),
        ("MSBADGES:START", "MSBADGES:END"),
    ],
)
def test_generated_markers_are_unique_and_ordered(start: str, end: str) -> None:
    text = _text()
    a, b = f"<!-- {start} -->", f"<!-- {end} -->"
    assert text.count(a) == 1 and text.count(b) == 1
    assert text.index(a) < text.index(b)


def test_generated_blocks_are_current_update_readme_results_check_is_zero() -> None:
    assert urr.main(["--check"]) == 0


# C9, C15: every number has a source ---------------------------------------------------------


def _summary() -> dict[str, Any]:
    data: dict[str, Any] = json.loads(SUMMARY.read_text(encoding="utf-8"))
    return data


def test_c9_eval_numbers_match_the_versioned_summary() -> None:
    """C9/C15: every eval figure in the README (generated block, table, Spanish summary)
    equals tests/eval/results.summary.json."""
    s, text = _summary(), _text()
    m = s["metrics"]
    block = text.split("<!-- RESULTS:START -->")[1].split("<!-- RESULTS:END -->")[0]
    for key, label in urr.METRIC_LABELS.items():
        want = f"| {label} | {m[key]['passed']}/{m[key]['total']} ({m[key]['pct']}%) |"
        assert want in block, want
    latency = f"p50 {s['latency_ms']['p50']} ms, p95 {s['latency_ms']['p95']} ms"
    assert text.count(latency) == 2, f"latency shown {text.count(latency)} times (block + table)"
    assert f"**{s['passed']} of {s['total']}** ({m['aprobados']['pct']}%)" in text
    assert f"{s['passed']} de {s['total']} casos" in _section(SPANISH_SECTION)
    failed = [k for k, v in s["cases"].items() if v != "pasó"]
    assert ("Failed cases: none." in block) == (not failed)
    assert f"Local evaluation of {s['total']} cases" in block


def _declared_coverage() -> float:
    procedure = PROCEDURE.read_text(encoding="utf-8")
    m = re.search(r"Calidad de código[^\n]*?\|\s*(\d+(?:\.\d+)?)%,", procedure)
    assert m, "docs/testing-procedure.md declares no coverage"
    return float(m.group(1))


def test_c9_coverage_everywhere_matches_testing_procedure() -> None:
    """Badge, results table and Spanish summary show the coverage declared in the procedure
    (pytest is not run here; the procedure is the declared measurement)."""
    text, declared = _text(), _declared_coverage()
    badge = re.search(r"badge/coverage-(\d+(?:\.\d+)?)%25", text)
    table = re.search(r"`src/` coverage \| (\d+(?:\.\d+)?)%", text)
    spanish = re.search(r"(\d+(?:\.\d+)?)% de cobertura", _section(SPANISH_SECTION))
    assert badge and table and spanish
    assert {float(badge[1]), float(table[1]), float(spanish[1])} == {declared}


def test_c9_test_counts_match_testing_procedure() -> None:
    text = _text()
    procedure = PROCEDURE.read_text(encoding="utf-8")
    declared = re.search(r"(\d+) passed, (\d+) skipped, (\d+) deselected", procedure)
    shown = re.search(r"(\d+) run, (\d+) skipped, (\d+) deselected", text)
    assert declared and shown
    assert shown.groups() == declared.groups(), f"README {shown.groups()} vs {declared.groups()}"


def test_c9_business_case_numbers_exist_in_business_case_doc() -> None:
    doc = BUSINESS_CASE.read_text(encoding="utf-8")
    row = next(r for r in _text().splitlines() if r.startswith("| Repetitive"))
    assert "39.92%" in row and "39.92" in doc
    for figure in ("51.24%", "1.90", "79.50", "60.57", "35.6", "53.4", "71.2"):
        assert figure in doc, f"{figure} not in docs/business-case.md"
        assert figure in _text(), f"{figure} not in README"


def test_c9_reranker_size_claim_matches_adr() -> None:
    """The '~0.57 GB' download is the ADR-0009 figure; README repeats it consistently."""
    adr = (PROJECT_ROOT / "docs" / "adr" / "0009-veto-con-reranker-cross-encoder.md").read_text(
        "utf-8"
    )
    assert "0.57 GB" in adr
    assert len(re.findall(r"~0\.57 GB", _text())) >= 2
    assert not re.search(r"~0\.(?!57)\d+ GB", _text())


# C19 and honesty: Microsoft status --------------------------------------------------------------


def test_c19_microsoft_badges_and_status_follow_validation_json_and_are_not_green() -> None:
    """C19 [Wei]: badges carry real status. While Fabric/Copilot Studio are 'pendiente' in
    docs/validation-status.json no Microsoft badge is green and the table says pending."""
    status = {i["id"]: i for i in json.loads(STATUS.read_text(encoding="utf-8"))}
    text = _text()
    badges = text.split("<!-- MSBADGES:START -->")[1].split("<!-- MSBADGES:END -->")[0]
    table = text.split("<!-- VALIDATION:START -->")[1].split("<!-- VALIDATION:END -->")[0]
    for key, label in (("fabric", "Fabric"), ("copilot_studio", "Copilot Studio")):
        line = next(ln for ln in badges.splitlines() if ln.startswith(f"![{label}"))
        green = bool(re.search(r"2EA043|brightgreen|success", line, re.I))
        assert green == (status[key]["estado"] == "validado"), line
        if status[key]["estado"] == "pendiente":
            assert "pending validation" in line.lower()
    pending = [i for i in status.values() if i["estado"] == "pendiente"]
    assert table.count("⏳ Pending validation on a real tenant") == len(pending)
    assert "✅" not in table or any(i["estado"] == "validado" for i in status.values())
    assert "Fabric and Copilot Studio are designed but not yet validated on a real tenant" in text


def test_c9_cli_subcommands_cited_in_the_structure_block_equal_the_parser() -> None:
    """The repo-structure block and the command table cite exactly the real subcommands."""
    cited = set(re.findall(r"python main\.py ([a-z][a-z-]*)", _text()))
    assert cited == set(main.SUBCOMMANDS)
