"""Audit of the feature-loop project skill against the official format and the user's request.

The skill is never edited here: a mismatch fails the test. Format and limits come from
``docs/research/project-skills.md``.
"""

from __future__ import annotations

import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
SKILL_DIR = ROOT / ".claude" / "skills" / "feature-loop"
SKILL = SKILL_DIR / "SKILL.md"
AGENTS_DIR = ROOT / ".claude" / "agents"

DESCRIPTION = (
    "Úsala para desarrollar cualquier feature del roadmap de DeskPilot AI de punta a punta "
    "con el ciclo a–f."
)
# Frontmatter fields documented in docs/research/project-skills.md (b).
DOCUMENTED_FIELDS = {
    "name", "description", "when_to_use", "argument-hint", "arguments",
    "disable-model-invocation", "user-invocable", "allowed-tools", "disallowed-tools",
    "model", "effort", "context", "agent", "background", "hooks", "paths", "shell",
    "metadata", "license", "compatibility",
}  # fmt: skip
STEP_RE = re.compile(r"^### ([a-f])\) ", re.MULTILINE)


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _split() -> tuple[dict[str, object], str]:
    text = _text(SKILL)
    assert text.startswith("---\n"), "SKILL.md must start with YAML frontmatter"
    _, front, body = text.split("---\n", 2)
    data = yaml.safe_load(front)
    assert isinstance(data, dict)
    return data, body


def _step(letter: str) -> str:
    """Return the text of step ``letter`` (from its heading to the next heading)."""
    body = _split()[1]
    m = re.search(rf"^### {letter}\) .*?(?=^##+ |\Z)", body, re.MULTILINE | re.DOTALL)
    assert m, f"step {letter}) missing"
    return m.group(0)


def _agent_files() -> set[str]:
    return {p.stem for p in AGENTS_DIR.glob("*.md")}


def test_frontmatter_has_only_documented_fields() -> None:
    data, _ = _split()
    assert set(data) <= DOCUMENTED_FIELDS, set(data) - DOCUMENTED_FIELDS
    assert {"name", "description", "argument-hint"} <= set(data)


def test_name_matches_folder_and_is_kebab_case() -> None:
    data, _ = _split()
    assert data["name"] == SKILL_DIR.name == "feature-loop"
    assert re.fullmatch(r"[a-z0-9]+(-[a-z0-9]+)*", str(data["name"]))


def test_description_exact_and_within_limit() -> None:
    data, _ = _split()
    assert data["description"] == DESCRIPTION
    assert len(str(data["description"])) < 1536


def test_argument_hint_present_and_skill_uses_arguments() -> None:
    data, body = _split()
    assert str(data["argument-hint"]).strip()
    assert "$ARGUMENTS" in body
    assert "docs/roadmap.md" in body


def test_skill_under_500_lines() -> None:
    assert len(_text(SKILL).splitlines()) < 500


def test_steps_a_to_f_in_order_exactly_once() -> None:
    assert STEP_RE.findall(_split()[1]) == list("abcdef")


def test_step_a_branching_and_state() -> None:
    s = _step("a")
    assert "reference/branch-naming.md" in s
    assert all(p in s for p in ("feat/", "fix/", "chore/"))
    assert "en desarrollo" in s


def test_step_b_forbids_touching_tests() -> None:
    s = _step("b")
    assert re.search(r"[Pp]rohibido tocar `tests/`", s)
    assert "subagente" in s.lower()


def test_step_c_independent_qa_tester_and_anti_fake_rules() -> None:
    s = _step("c")
    assert "qa-tester" in s
    assert "DISTINTO" in s
    assert "Anti-falseo" in s
    assert "skip" in s and "xfail" in s
    assert "se corrige el CÓDIGO, no la prueba" in s


def test_step_d_verification_rules() -> None:
    s = _step("d")
    for cmd in ("pytest --cov=src", "ruff check", "mypy"):
        assert cmd in s
    assert "Máximo 2 ciclos" in s
    assert "bloqueada" in s
    assert "security-verifier" in s
    assert "[ALTO RIESGO]" in s


def test_step_e_documentation() -> None:
    s = _step("e")
    assert "docs/features/<feature>.md" in s
    assert "CHANGELOG" in s
    assert "templates/feature-doc.md" in s


def test_step_f_merge_rules() -> None:
    s = _step("f")
    assert "CI verde" in s
    assert "gh pr merge --merge" in s
    assert "--delete-branch" in s  # deletes the branch
    assert "mergeada" in s
    assert "Log" in s
    assert "templates/pr-checklist.md" in s


def test_research_rule_uses_researcher_and_docs_research() -> None:
    body = _split()[1]
    section = body.split("## Regla estricta de investigación", 1)[1].split("\n## ", 1)[0]
    assert "researcher" in section
    assert "docs/research/" in section


def test_checkpoint_section() -> None:
    body = _split()[1]
    assert "## Checkpoint" in body
    assert "Tras cada merge" in body
    assert "Log" in body


def test_orchestrator_rules() -> None:
    body = _split()[1]
    section = body.split("## Reglas del orquestador", 1)[1].split("\n## ", 1)[0]
    assert "Delega TODO a subagentes" in section
    assert "uno a la vez" in section
    assert "≤10 líneas" in section
    assert "UNA línea" in section


def test_subagents_named_in_skill_exist() -> None:
    body = _split()[1]
    existing = _agent_files()
    listed = re.search(r"Subagente del área \(([^)]*)\)", _step("b"))
    assert listed
    area = {n.strip() for n in listed.group(1).split(",")}
    assert area, "no area agents listed"
    assert area <= existing, area - existing
    for role in ("qa-tester", "researcher", "security-verifier", "docs-writer"):
        assert role in body
        assert role in existing
    pattern = r"\b[a-z]+(?:-[a-z]+)*-(?:engineer|writer|tester|verifier|designer|architect)\b"
    tokens = set(re.findall(pattern, body))
    assert tokens <= existing, tokens - existing


def test_reference_agents_roles_match_agent_files_both_ways() -> None:
    text = _text(SKILL_DIR / "reference" / "agents.md")
    rows = re.findall(r"^\| ([a-z-]+) \|.*`\.claude/agents/([a-z-]+)\.md`", text, re.MULTILINE)
    roles = {r for r, _ in rows}
    assert roles
    assert all(role == fname for role, fname in rows)
    assert roles == _agent_files()


def test_supporting_files_referenced_exist() -> None:
    body = _split()[1]
    links = re.findall(r"\]\(([^)#]+)\)", body)
    assert links
    for link in links:
        assert (SKILL_DIR / link).is_file(), link
    for needed in (
        "templates/feature-doc.md",
        "templates/pr-checklist.md",
        "reference/agents.md",
        "reference/branch-naming.md",
    ):
        assert needed in body
        assert (SKILL_DIR / needed).is_file()


def test_feature_doc_template_has_pruebas_realizadas() -> None:
    text = _text(SKILL_DIR / "templates" / "feature-doc.md")
    assert re.search(r"^## .*[Pp]ruebas realizadas", text, re.MULTILINE)


def test_feature_doc_template_required_sections() -> None:
    text = _text(SKILL_DIR / "templates" / "feature-doc.md")
    headings = " | ".join(re.findall(r"^## (.+)$", text, re.MULTILINE)).lower()
    parts = ("qué", "specs", "pruebas realizadas", "resultados reales", "cómo verificar", "limitaciones")
    for part in parts:
        assert part in headings, part
    assert "RF" in text  # specs / requirements covered


def test_pr_checklist_covers_pr_template_checklist() -> None:
    tpl = _text(ROOT / ".github" / "pull_request_template.md")
    sections = re.findall(r"^## (.+)$", tpl, re.MULTILINE)
    assert sections == [
        "Qué cambia",
        "Por qué",
        "Cómo se probó",
        "Capturas o salida relevante",
        "Checklist",
    ]
    assert tpl.rstrip().endswith("Closes #")
    cl = _text(SKILL_DIR / "templates" / "pr-checklist.md")
    for key in (
        "ruff check",
        "ruff format --check",
        "mypy",
        "80%",
        "secretos",
        "400 líneas",
        "docs/sources.md",
        "CHANGELOG",
        "CI verde",
        "Closes #n",
    ):
        assert key in cl, key
    assert "- [ ]" in cl


def test_pr_checklist_has_same_sections_as_template() -> None:
    tpl = _text(ROOT / ".github" / "pull_request_template.md")
    cl = _text(SKILL_DIR / "templates" / "pr-checklist.md")
    for sec in re.findall(r"^## (.+)$", tpl, re.MULTILINE):
        assert sec in cl, sec


def test_branch_naming_reference_matches_research() -> None:
    ref = _text(SKILL_DIR / "reference" / "branch-naming.md")
    research = _text(ROOT / "docs" / "research" / "branch-and-feature-naming.md")
    assert "docs/research/branch-and-feature-naming.md" in ref
    for prefix in ("feat/", "fix/", "chore/"):
        assert prefix in ref
        assert prefix in research
    assert "kebab-case" in ref


def test_skill_has_no_scratchpad_paths_secrets_or_emails() -> None:
    forbidden = [
        r"AppData",
        r"\\Temp\\",
        r"/tmp/",
        r"claude[\\/]C--",
        r"scratchpad",
        r"[\w.+-]+@[\w-]+\.[\w.]+",
        r"sk-[A-Za-z0-9]{10,}",
        r"ghp_[A-Za-z0-9]{10,}",
        r"(?i)(api[_-]?key|password|token)\s*[:=]\s*\S{8,}",
    ]
    for path in SKILL_DIR.rglob("*"):
        if path.is_file():
            text = _text(path)
            for pat in forbidden:
                assert not re.search(pat, text), (path.name, pat)


def test_claude_md_and_contributing_reference_skill() -> None:
    claude = _text(ROOT / "CLAUDE.md")
    contributing = _text(ROOT / "CONTRIBUTING.md")
    assert re.search(r"usa la skill feature-loop", claude)
    assert ".claude/skills/" in claude
    assert ".claude/skills/" in contributing


def test_cited_commands_exist() -> None:
    body = _text(SKILL)
    for cmd in ("gh pr merge --merge", "ruff check", "mypy", "pytest"):
        assert cmd in body
    pyproject = _text(ROOT / "pyproject.toml")
    assert "ruff" in pyproject and "mypy" in pyproject and "pytest" in pyproject
