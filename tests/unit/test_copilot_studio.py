"""Structure and consistency of the Copilot Studio agent design (T20).

Validates integrations/copilot_studio/ against openapi.json, the MCP tool names,
the retrieval escalation policy and the requirements (RN-01, RN-03, RN-05).
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from src.api.classification import classify
from src.api.mcp_server import TOOL_NAMES
from src.llm import NoLLM
from src.retrieval.policy import EscalationReason, escalation_reason

ROOT = Path(__file__).resolve().parents[2] / "integrations" / "copilot_studio"
TOPIC_FILES = sorted((ROOT / "topics").glob("*.md"))
SNAKE = re.compile(r"^[a-z][a-z0-9]*(?:_[a-z0-9]+)*$")
MAX_PHRASE_CHARS = 80
MAX_INSTRUCTIONS_CHARS = 4000
VERIFY = "⚠ verificar en pantalla"


def _read(name: str) -> str:
    return (ROOT / name).read_text(encoding="utf-8")


def _parse_topic(path: Path) -> dict[str, object]:
    text = path.read_text(encoding="utf-8")
    match = re.match(r"^---\n(.*?)\n---\n", text, re.DOTALL)
    assert match, f"{path.name}: missing frontmatter"
    data: dict[str, object] = {}
    key: str | None = None
    for line in match.group(1).splitlines():
        if line.startswith("  - "):
            assert key is not None
            items = data[key]
            assert isinstance(items, list)
            items.append(line[4:].strip())
        else:
            key, _, value = line.partition(":")
            value = value.strip()
            if value == "":
                data[key] = []
            elif value.startswith("["):
                data[key] = [v.strip() for v in value.strip("[]").split(",") if v.strip()]
            else:
                data[key] = value
    return data


TOPICS = {p.name: _parse_topic(p) for p in TOPIC_FILES}


def _list(topic: str, key: str) -> list[str]:
    value = TOPICS[topic][key]
    assert isinstance(value, list)
    return [str(v) for v in value]


def test_eight_topics_present() -> None:
    assert len(TOPICS) == 8


@pytest.mark.parametrize("fname", sorted(TOPICS))
def test_topic_frontmatter(fname: str) -> None:
    topic = TOPICS[fname]
    assert SNAKE.match(str(topic["name"])), topic["name"]
    assert len(str(topic["description"])) >= 40
    assert topic["languages"] == ["es", "en"]
    for key in ("trigger_phrases_es", "trigger_phrases_en"):
        phrases = _list(fname, key)
        assert phrases, f"{fname}: {key} empty"
        assert len(phrases) < 200
        assert all(p.strip() for p in phrases)
        assert all(len(p) <= MAX_PHRASE_CHARS for p in phrases), fname
        assert len({p.lower() for p in phrases}) == len(phrases), f"{fname}: duplicates"
    assert _list(fname, "requirements")


def test_topic_names_unique() -> None:
    names = [str(t["name"]) for t in TOPICS.values()]
    assert len(set(names)) == len(names)


def test_no_duplicate_phrases_across_topics() -> None:
    seen: dict[str, str] = {}
    for fname in TOPICS:
        for key in ("trigger_phrases_es", "trigger_phrases_en"):
            for phrase in _list(fname, key):
                norm = phrase.lower().strip("¿?¡! .")
                assert norm not in seen, f"{phrase!r} in {fname} and {seen[norm]}"
                seen[norm] = fname


def _operation_ids() -> set[str]:
    spec = json.loads(_read("openapi.json"))
    return {
        op["operationId"]
        for methods in spec["paths"].values()
        for op in methods.values()
        if isinstance(op, dict) and "operationId" in op
    }


def test_openapi_mcp_and_tools_md_agree() -> None:
    tools_md = _read("tools.md")
    assert _operation_ids() == set(TOOL_NAMES)
    for tool in TOOL_NAMES:
        assert f"`{tool}`" in tools_md


@pytest.mark.parametrize("fname", sorted(TOPICS))
def test_topic_tools_exist_everywhere(fname: str) -> None:
    tools_md = _read("tools.md")
    for tool in _list(fname, "tools"):
        assert tool in _operation_ids(), f"{fname}: {tool} not in openapi.json"
        assert tool in TOOL_NAMES
        assert f"`{tool}`" in tools_md


def test_every_tool_used_by_some_topic() -> None:
    used = {t for f in TOPICS for t in _list(f, "tools")}
    assert used == set(TOOL_NAMES)


def test_instructions_content() -> None:
    text = _read("instructions.md")
    low = text.lower()
    assert len(text) <= MAX_INSTRUCTIONS_CHARS
    for word in ("fraude", "acceso no autorizado", "caja"):
        assert word in low
    assert "rn-03" in low
    assert re.search(r"nunca pidas contraseñas?.*nip.*tarjeta", low)
    assert "no tienes la respuesta" in low
    assert "cita" in low and re.search(r"KB-\d{3}", text)
    assert "español" in low and "inglés" in low
    for tool in TOOL_NAMES:
        assert tool in text


def test_escalation_sla_and_messages() -> None:
    text = _read("escalation.md")
    rows = dict(re.findall(r"^\| (P[1-4]) \|.*\| (\d+) h \|$", text, re.MULTILINE))
    assert rows == {"P1": "4", "P2": "8", "P3": "24", "P4": "72"}
    p1 = text.split("## P1 obligatorio")[1].split("##")[0]
    assert re.search(r"^- ES: .*P1.*4 horas", p1, re.MULTILINE)
    assert re.search(r"^- EN: .*P1.*4 hours", p1, re.MULTILINE)
    for section in ("Humano (a petición)", "Ticket normal por prioridad"):
        body = text.split(f"## {section}")[1].split("##")[0]
        assert "- ES:" in body and "- EN:" in body
        assert "{ticket_id}" in body and "{sla_horas}" in body


def test_instructions_sla_matches_escalation() -> None:
    assert "P1 4 h, P2 8 h, P3 24 h, P4 72 h" in _read("instructions.md")


def test_conversations_coverage() -> None:
    text = _read("test-conversations.md")
    cases = re.findall(r"^## (CT-\d{2}) \((ES|EN|ES/EN)\) (.+)$", text, re.MULTILINE)
    ids = [c[0] for c in cases]
    assert len(ids) >= 12
    assert len(set(ids)) == len(ids)
    assert {"ES", "EN"} <= {c[1] for c in cases}
    titles = " ".join(c[2].lower() for c in cases)
    for keyword in ("fraude", "pegad", "fuera de alcance", "no lo sé"):
        assert keyword in titles, keyword
    for case_id in ids:
        block = text.split(f"## {case_id}")[1].split("\n## ")[0]
        assert "- Usuario:" in block and "- Debe:" in block and "- No debe:" in block


def _all_files() -> list[Path]:
    return [p for p in ROOT.rglob("*") if p.is_file() and p.name != ".gitkeep"]


def _luhn(digits: str) -> bool:
    total = 0
    for i, ch in enumerate(reversed(digits)):
        d = int(ch)
        if i % 2:
            d = d * 2 - 9 if d * 2 > 9 else d * 2
        total += d
    return total % 10 == 0


def test_no_secrets_or_real_data() -> None:
    curp = re.compile(r"\b[A-Z]{4}\d{6}[HM][A-Z]{5}[A-Z0-9]\d\b")
    key = re.compile(r"\b(?:sk-[A-Za-z0-9]{20,}|AKIA[0-9A-Z]{16}|[A-Za-z0-9]{32,})\b")
    email = re.compile(r"[\w.+-]+@(?:[\w-]+\.)+[a-z]{2,}", re.IGNORECASE)
    card = re.compile(r"\b(?:\d[ -]?){13,19}\b")
    allowed_card = "4111 1111 1111 1111"  # documented synthetic test number (CT-08)
    for path in _all_files():
        text = path.read_text(encoding="utf-8")
        assert not curp.search(text), path.name
        assert not key.search(text), f"{path.name}: key-like token"
        for m in email.finditer(text):
            assert m.group(0).endswith("example.com"), (path.name, m.group(0))
        for m in card.finditer(text):
            if m.group(0).strip() == allowed_card:
                assert path.name == "test-conversations.md"
                continue
            digits = re.sub(r"\D", "", m.group(0))
            assert not _luhn(digits), f"{path.name}: Luhn-valid number {m.group(0)}"


def test_verify_markers_where_research_requires() -> None:
    assert VERIFY in _read("README.md")  # instructions character limit
    assert VERIFY in _read("tools.md")  # tool name/description length
    assert VERIFY in _read("escalation.md")  # Escalate system topic / handoff
    topics_text = " ".join(p.read_text(encoding="utf-8") for p in TOPIC_FILES)
    assert VERIFY in topics_text  # trigger phrases under generative orchestration


def test_language_support_verify_marker() -> None:
    docs = " ".join(p.read_text(encoding="utf-8") for p in _all_files() if p.suffix == ".md")
    assert re.search(r"idiomas? soportados|language support", docs, re.IGNORECASE), (
        "ES/EN language support still needs a verify marker"
    )


def _reasons(key: str) -> set[EscalationReason]:
    found: set[EscalationReason] = set()
    for phrase in _list("escalamiento-obligatorio.md", key):
        reason = escalation_reason(phrase)
        if reason:
            found.add(reason)
    return found


@pytest.mark.parametrize("key", ["trigger_phrases_es", "trigger_phrases_en"])
def test_escalation_phrases_trigger_each_rn03_type(key: str) -> None:
    assert _reasons(key) >= {"fraud", "unauthorized_access", "cash_system"}


@pytest.mark.parametrize("key", ["trigger_phrases_es", "trigger_phrases_en"])
def test_every_escalation_phrase_escalates(key: str) -> None:
    phrases = _list("escalamiento-obligatorio.md", key)
    assert phrases
    for phrase in phrases:
        assert escalation_reason(phrase) is not None, phrase


@pytest.mark.parametrize("key", ["trigger_phrases_es", "trigger_phrases_en"])
def test_every_escalation_phrase_creates_p1_escalated_ticket(key: str) -> None:
    for phrase in _list("escalamiento-obligatorio.md", key):
        result = classify(phrase, NoLLM(), 5.0)
        assert result.prioridad == "P1", phrase
        assert result.escalated, phrase
