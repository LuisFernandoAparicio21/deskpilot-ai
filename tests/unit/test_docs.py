"""Documentation audit (T24): README and docs are checked against the real repo.

Links, anchors, CLI commands, mermaid diagrams, eval figures, roadmap states and the learning
log template are verified against files, ``main.build_parser`` and
``tests/eval/results.summary.json``. Docs are never edited here: a mismatch fails with
"doc vs real".
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path
from urllib.parse import unquote

import pytest

import main
from src.utils.config import PROJECT_ROOT

README = PROJECT_ROOT / "README.md"
DOCS = PROJECT_ROOT / "docs"
SUMMARY = PROJECT_ROOT / "tests" / "eval" / "results.summary.json"
NOTE = "Datos sintéticos generados para este proyecto; las cifras son ilustrativas"

FENCE = "`" * 3
LINK_RE = re.compile(r"!?\[[^\]]*\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)")
FENCE_RE = re.compile(r"^" + FENCE + r".*?^" + FENCE, re.S | re.M)


def _doc_files() -> list[Path]:
    return [README, *sorted(DOCS.rglob("*.md"))]


def _rel(path: Path) -> str:
    return path.relative_to(PROJECT_ROOT).as_posix()


def _strip_code(text: str) -> str:
    """Remove fenced blocks and inline code spans so example syntax is not read as links."""
    return re.sub(r"`[^`\n]*`", "", FENCE_RE.sub("", text))


def _slug(heading: str) -> str:
    """GitHub heading anchor: lowercase, drop punctuation, spaces to hyphens."""
    text = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", heading.strip().lower())
    text = re.sub(r"[`*_]", "", text)
    text = re.sub(r"[^\w\- ]", "", text, flags=re.UNICODE)
    return text.replace(" ", "-")


def _anchors(path: Path) -> set[str]:
    body = FENCE_RE.sub("", path.read_text(encoding="utf-8"))
    seen: dict[str, int] = {}
    result: set[str] = set()
    for match in re.finditer(r"^#{1,6}\s+(.+?)\s*#*$", body, re.M):
        slug = _slug(match.group(1))
        count = seen.get(slug, 0)
        result.add(slug if count == 0 else f"{slug}-{count}")
        seen[slug] = count + 1
    return result


def _links(path: Path) -> list[str]:
    return LINK_RE.findall(_strip_code(path.read_text(encoding="utf-8")))


def _is_external(target: str) -> bool:
    return bool(re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*:", target)) or target.startswith("//")


def _table_rows(text: str) -> list[list[str]]:
    rows = []
    for line in text.splitlines():
        if line.startswith("|") and not re.match(r"^\|[\s:|-]+\|?$", line):
            rows.append([c.strip() for c in line.strip().strip("|").split("|")])
    return rows


def _section(text: str, heading: str) -> str:
    match = re.search(rf"^##\s+{re.escape(heading)}\s*$(.*?)(?=^##\s|\Z)", text, re.S | re.M)
    assert match, f"section '## {heading}' missing"
    return match.group(1)


# (1) links -----------------------------------------------------------------------------


@pytest.mark.parametrize("doc", _doc_files(), ids=_rel)
def test_relative_links_resolve(doc: Path) -> None:
    broken: list[str] = []
    for target in _links(doc):
        if _is_external(target):
            continue
        raw_path, _, fragment = target.partition("#")
        dest = doc if not raw_path else (doc.parent / unquote(raw_path)).resolve()
        if not dest.exists():
            broken.append(f"{target}: expected existing file, real: {dest} missing")
            continue
        if fragment and dest.suffix == ".md" and fragment.lower() not in _anchors(dest):
            broken.append(f"{target}: expected anchor '#{fragment}' in {_rel(dest)}")
    assert not broken, f"{_rel(doc)} broken links:\n" + "\n".join(broken)


def test_link_extractor_sees_links() -> None:
    assert len(_links(README)) > 20
    assert {"setup", "licencia", "por-qué-este-proyecto"} <= _anchors(README)


def test_link_checker_detects_broken_target(tmp_path: Path) -> None:
    doc = tmp_path / "x.md"
    doc.write_text("# T\n[a](missing.md) [b](#nope) [c](#t)\n", encoding="utf-8")
    assert _links(doc) == ["missing.md", "#nope", "#t"]
    assert _anchors(doc) == {"t"}


# (2) README content --------------------------------------------------------------------


def test_readme_required_content() -> None:
    text = README.read_text(encoding="utf-8")
    assert f"**{NOTE}.**" in text
    for heading in ("Por qué este proyecto", "Habilidades demostradas", "English summary"):
        assert re.search(rf"^##\s+{heading}\s*$", text, re.M), f"missing section {heading}"
    video = _section(text, "Video")
    assert "PLACEHOLDER" in video and "http" not in video, "video must stay a placeholder"
    english = _section(text, "English summary")
    assert len(english.split()) > 60 and "synthetic" in english


# (3) CLI commands ----------------------------------------------------------------------


def _readme_commands() -> list[tuple[str, list[str]]]:
    found: list[tuple[str, list[str]]] = []
    text = README.read_text("utf-8")
    for match in re.finditer(r"python main\.py ([a-z][a-z-]*)([^`\n|]*)", text):
        found.append((match.group(1), re.findall(r"--[a-z][a-z-]*", match.group(2))))
    return found


def test_readme_commands_exist_in_parser() -> None:
    commands = _readme_commands()
    assert {c for c, _ in commands} >= {"generate-data", "serve", "mcp", "eval"}
    parser = main.build_parser()
    for name, _flags in commands:
        assert name in main.SUBCOMMANDS, f"README cites unknown subcommand {name}"
        with pytest.raises(SystemExit) as exc:
            parser.parse_args([name, "--help"])
        assert exc.value.code == 0


def test_readme_documented_subcommands_cover_parser() -> None:
    cited = {c for c, _ in _readme_commands()}
    real = set(main.SUBCOMMANDS)
    assert cited == real, f"README {sorted(cited)} vs parser {sorted(real)}"


@pytest.mark.parametrize("name", sorted({c for c, _ in _readme_commands()}))
def test_readme_flags_exist_in_real_help(name: str) -> None:
    flags = {f for c, fl in _readme_commands() if c == name for f in fl}
    out = subprocess.run(
        [sys.executable, "main.py", name, "--help"],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        timeout=120,
        check=True,
    ).stdout
    missing = sorted(f for f in flags if f not in out)
    assert not missing, f"README cites {missing} for '{name}' but --help shows none"


# (4) job-fit ---------------------------------------------------------------------------


def test_job_fit_covers_eleven_points_with_existing_evidence() -> None:
    path = DOCS / "job-fit.md"
    rows = [r for r in _table_rows(path.read_text("utf-8")) if r[0].isdigit()]
    assert [int(r[0]) for r in rows] == list(range(1, 12)), "expected points 1..11 once each"
    for row in rows:
        assert len(row) == 4 and all(row), f"point {row[0]}: empty cell"
        local = [t for t in LINK_RE.findall(row[2]) if not _is_external(t)]
        assert local, f"point {row[0]}: no evidence link"
        for target in local:
            assert (path.parent / target.partition("#")[0]).resolve().exists(), (
                f"point {row[0]}: evidence {target} missing"
            )
        assert re.match(r"(Hecho|Parcial|Pendiente manual)", row[3]), (
            f"point {row[0]}: state '{row[3]}' outside legend"
        )


# (5) mermaid ---------------------------------------------------------------------------


def _mermaid_blocks(path: Path) -> list[str]:
    text = path.read_text("utf-8")
    fences = len(re.findall(r"^" + FENCE, text, re.M))
    assert fences % 2 == 0, f"{_rel(path)}: unbalanced code fences ({fences})"
    return re.findall(r"^" + FENCE + r"mermaid\n(.*?)^" + FENCE, text, re.S | re.M)


def _md_with_mermaid() -> list[Path]:
    return [p for p in _doc_files() if FENCE + "mermaid" in p.read_text("utf-8")]


def test_mermaid_present_in_readme_and_architecture() -> None:
    names = {p.name for p in _md_with_mermaid()}
    assert {"README.md", "architecture.md"} <= names


@pytest.mark.parametrize("doc", _md_with_mermaid(), ids=_rel)
def test_mermaid_blocks_are_balanced(doc: Path) -> None:
    blocks = _mermaid_blocks(doc)
    assert blocks
    for block in blocks:
        assert re.match(r"\s*(flowchart|sequenceDiagram|graph|stateDiagram)", block)
        code = re.sub(r'"[^"]*"', "", block)
        opens = len(re.findall(r"^\s*(?:subgraph|alt|opt|loop|par|rect)\b", code, re.M))
        ends = len(re.findall(r"^\s*end\s*$", code, re.M))
        assert opens == ends, f"{_rel(doc)}: {opens} openers vs {ends} 'end'"
        for left, right in ("[]", "()", "{}"):
            assert code.count(left) == code.count(right), f"{_rel(doc)}: unbalanced {left}{right}"


def _module_exists(ref: str) -> bool:
    candidates = [PROJECT_ROOT / ref, PROJECT_ROOT / "src" / ref]
    if "/" not in ref:
        candidates += list((PROJECT_ROOT / "src").rglob(ref))
    return any(c.is_file() for c in candidates)


@pytest.mark.parametrize("doc", _md_with_mermaid(), ids=_rel)
def test_mermaid_cited_modules_exist(doc: Path) -> None:
    refs = {r for b in _mermaid_blocks(doc) for r in re.findall(r"[\w/]+\.py\b", b)}
    missing = sorted(r for r in refs if not _module_exists(r))
    assert not missing, f"{_rel(doc)} cites modules that do not exist: {missing}"


def test_architecture_cited_python_files_exist() -> None:
    text = (DOCS / "architecture.md").read_text("utf-8")
    refs = set(re.findall(r"(?<![\w/.-])([\w/]+\.py)\b", text))
    assert {"mcp_server.py", "answer_service.py", "utils/redaction.py"} <= refs
    missing = sorted(r for r in refs if not _module_exists(r))
    assert not missing, f"architecture.md cites missing files: {missing}"


# (6) eval figures ----------------------------------------------------------------------


def test_readme_eval_figures_match_summary() -> None:
    s = json.loads(SUMMARY.read_text("utf-8"))
    m = s["metrics"]
    text = README.read_text("utf-8")
    rows = _table_rows(text)
    row = next(r for r in rows if r[0] == "Casos de evaluación")[1]
    assert f"{s['passed']} de {s['total']}" in row
    assert f"{m['aprobados']['pct']}%" in row
    assert f"top-3 {m['retrieval_top3']['passed']}/{m['retrieval_top3']['total']}" in row
    assert f"rechazo {m['rechazo']['passed']}/{m['rechazo']['total']}" in row
    assert f"clasificación {m['clasificacion']['passed']}/{m['clasificacion']['total']}" in row
    assert f"seguridad {m['seguridad']['passed']}/{m['seguridad']['total']}" in row
    lat = next(r for r in rows if r[0].startswith("Latencia"))[1]
    assert f"p50 {s['latency_ms']['p50']} ms" in lat
    assert f"p95 {s['latency_ms']['p95']} ms" in lat
    assert f"{s['passed']}/{s['total']} cases pass" in text
    failed = [k for k, v in s["cases"].items() if v != "pasó"]
    assert failed == ["EV-16"], f"README documents EV-16 as the only failure; real: {failed}"
    assert "EV-16" in _section(text, "Límites conocidos")
    assert s["thresholds_met"] is False and "código 1" in text


# (7) roadmap ---------------------------------------------------------------------------


def test_roadmap_states_and_prs() -> None:
    text = (DOCS / "roadmap.md").read_text("utf-8")
    legend = _section(text, "Leyenda de estados")
    states = set(re.findall(r"`([^`]+)`", legend.splitlines()[1]))
    assert states == {"pendiente", "en desarrollo", "en pruebas", "documentada", "mergeada"}
    prs: list[str] = []
    rows_seen = 0
    for table in re.split(r"\n(?=## )", text):
        rows = _table_rows(table)
        if not rows or "Estado" not in rows[0]:
            continue
        head = rows[0]
        i_state, i_pr, i_date, i_branch = (head.index(c) for c in ("Estado", "PR", "Fecha", "Rama"))
        for row in rows[1:]:
            rows_seen += 1
            assert row[i_state] in states, f"{row[0]}: state '{row[i_state]}' outside legend"
            if row[i_state] != "mergeada" or "commit directo" in row[i_branch]:
                continue  # T1-T7 predate the PR flow by design
            assert re.fullmatch(r"#\d+", row[i_pr]), f"{row[0]}: mergeada without PR ({row[i_pr]})"
            assert re.fullmatch(r"\d{4}-\d{2}-\d{2}", row[i_date]), f"{row[0]}: no date"
            prs.append(row[i_pr])
    assert rows_seen >= 25
    assert len(prs) == len(set(prs)), f"duplicate PR numbers: {prs}"


# (8) learning log ----------------------------------------------------------------------


def test_learning_log_is_template_only() -> None:
    text = (DOCS / "learning-log.md").read_text("utf-8")
    assert "Plantilla" in text and "No contiene logros" in text
    assert not re.findall(r"\b(?:19|20)\d{2}-\d{2}-\d{2}\b", text), "real ISO date found"
    assert not re.findall(r"https?://", text), "real link found in template"
    for table in ("Rutas de aprendizaje", "Insignias y certificados"):
        rows = _table_rows(_section(text, table))[1:]
        assert rows, f"{table}: no rows"
        for row in rows:
            ok = row[0] == "(pendiente)" and not any(row[1:])
            assert ok, f"{table}: not a placeholder: {row}"
    block = _section(text, "Notas por fecha")
    assert "### AAAA-MM-DD" in block
    for line in re.findall(r"^- \*\*[^\n]*", block, re.M):
        assert re.search(r":(\*\*)?\s*$", line), f"note field is filled in: {line}"
    tail = _section(text, "Qué aprendí del proyecto")
    assert all(re.search(r":(\*\*)?\s*$", ln) for ln in tail.splitlines() if ln.startswith("- "))


# (9) secrets ---------------------------------------------------------------------------

SECRET_PATTERNS = {
    "openai/anthropic key": r"\bsk-[A-Za-z0-9_-]{16,}",
    "github token": r"\bgh[pousr]_[A-Za-z0-9]{20,}",
    "aws key": r"\bAKIA[0-9A-Z]{16}\b",
    "google key": r"\bAIza[0-9A-Za-z_-]{30,}",
    "private key": r"-----BEGIN [A-Z ]*PRIVATE KEY-----",
    "bearer": r"Bearer\s+[A-Za-z0-9._-]{20,}",
    "assignment": (
        r"(?i)\b(?:api[_-]?key|secret|password|token)\s*[=:]\s*['\"]?[A-Za-z0-9/+_-]{16,}"
    ),
    "guid": r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b",
    "connection string": r"(?i)(?:AccountKey|SharedAccessSignature)=[^\s]{8,}",
}
EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
SAFE_EMAIL = re.compile(r"(@example\.(?:com|org|net)$|^no-?reply@)")


@pytest.mark.parametrize("doc", _doc_files(), ids=_rel)
def test_no_secrets_or_real_emails(doc: Path) -> None:
    text = doc.read_text("utf-8")
    hits = [name for name, pat in SECRET_PATTERNS.items() if re.search(pat, text)]
    assert not hits, f"{_rel(doc)} matches secret patterns: {hits}"
    emails = [e for e in EMAIL_RE.findall(text) if not SAFE_EMAIL.search(e)]
    assert not emails, f"{_rel(doc)} contains non-placeholder emails: {emails}"


def test_secret_patterns_detect_samples() -> None:
    assert re.search(SECRET_PATTERNS["openai/anthropic key"], "sk-ant-abcdefghijklmnop1234")
    assert re.search(SECRET_PATTERNS["assignment"], "API_KEY=abcdefghijklmnop12345")
    assert not SAFE_EMAIL.search("real.person@gmail.com")
