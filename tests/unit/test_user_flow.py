"""User-flow docs audit: docs/user-flow.md and README "Cómo funciona" vs the real code.

Docs are never edited here: a mismatch fails with "doc vs real". Mermaid rendering itself
(mmdc) is not run; only structural checks by regex.
"""

from __future__ import annotations

import csv
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any

import pytest
import yaml

from src.api.mcp_server import TOOL_NAMES
from src.prompts.messages import NO_EVIDENCE
from src.utils.config import PROJECT_ROOT

FLOW = PROJECT_ROOT / "docs" / "user-flow.md"
README = PROJECT_ROOT / "README.md"
REQS = PROJECT_ROOT / "docs" / "requirements.md"
CASES = PROJECT_ROOT / "tests" / "eval" / "cases.csv"
CONFIG = PROJECT_ROOT / "config.yaml"
OPENAPI = PROJECT_ROOT / "integrations" / "copilot_studio" / "openapi.json"
KB_DIR = PROJECT_ROOT / "data" / "knowledge_base"
NOTE = "Datos sintéticos generados para este proyecto; las cifras son ilustrativas"

FENCE = "`" * 3
BLOCK_RE = re.compile(FENCE + r"(\w*)\n(.*?)\n" + FENCE, re.S)
TOOL_RE = re.compile(r"\b[a-z]+(?:_[a-z]+)+\b(?!\.py)")
LINK_RE = re.compile(r"!?\[[^\]]*\]\(([^)\s]+)\)")
KINDS = {"articulo", "rechazo", "escalamiento", "ticket", "seguridad"}

# Requirement keyword that must appear in the RF text for the step that cites it.
RF_KEYWORDS = {
    "RF-01": "idioma",
    "RF-02": "intención",
    "RF-03": "buscar_solucion",
    "RF-04": "Citar",
    "RF-05": "evidencia",
    "RF-06": "funcionó",
    "RF-07": "crear_ticket",
    "RF-08": "consultar_estado_ticket",
    "RF-09": "humano",
    "RF-10": "contraseñas",
    "RF-12": "relevantes",
    "RF-13": "umbral",
    "RF-14": "extractivo",
    "RF-16": "crear_ticket",
    "RF-17": "consultar_estado_ticket",
    "RF-18": "SQLite",
    "RF-19": "metricas_area",
}
# Table row (first-cell prefix) -> `esperado` kinds its EV-xx cases must have.
ROW_KINDS = {
    "Detectar idioma": {"articulo"},
    "Buscar solución": {"articulo"},
    "Sin evidencia": {"rechazo"},
    "Preguntar si funcionó": {"articulo"},
    "Crear ticket": {"ticket"},
    "Dato sensible": {"seguridad"},
    "Escalamiento obligatorio": {"escalamiento"},
    "Recuperar con umbral": {"articulo"},
    "Respuesta extractiva": {"articulo"},
    "Escribir en": {"ticket"},
}


def _readme_section() -> str:
    text = README.read_text(encoding="utf-8")
    match = re.search(r"^##\s+(?:\W+\s+)?Cómo funciona\s*$(.*?)(?=^## )", text, re.S | re.M)
    assert match, "README has no 'Cómo funciona' section"
    return match.group(1)


def _sources() -> dict[str, str]:
    return {
        "docs/user-flow.md": FLOW.read_text(encoding="utf-8"),
        "README.md#Cómo funciona": _readme_section(),
    }


def _mermaid(text: str) -> list[str]:
    return [body for lang, body in BLOCK_RE.findall(text) if lang == "mermaid"]


def _cases() -> dict[str, dict[str, str]]:
    with CASES.open(encoding="utf-8", newline="") as handle:
        return {row["id"]: row for row in csv.DictReader(handle)}


def _req_text() -> dict[str, str]:
    out: dict[str, str] = {}
    for line in REQS.read_text(encoding="utf-8").splitlines():
        match = re.match(r"- \*\*(RF-\d+)\*\*(.*)", line)
        if match:
            out[match.group(1)] = match.group(2)
    return out


def _table_rows(text: str) -> list[list[str]]:
    rows = []
    for line in text.splitlines():
        if line.startswith("|") and "---" not in line and "Paso del flujo" not in line:
            rows.append([c.strip() for c in line.strip().strip("|").split("|")])
    return rows


def _json_examples(text: str) -> list[dict[str, Any]]:
    out = []
    for lang, body in BLOCK_RE.findall(text):
        if lang == "json":
            out.append(json.loads(body))
    return out


def _config() -> dict[str, Any]:
    return yaml.safe_load(CONFIG.read_text(encoding="utf-8"))  # type: ignore[no-any-return]


# (1) Mermaid structure


@pytest.mark.parametrize("name", ["docs/user-flow.md", "README.md#Cómo funciona"])
def test_mermaid_blocks_open_and_close(name: str) -> None:
    text = _sources()[name]
    assert text.count(FENCE) % 2 == 0, f"{name}: unbalanced code fences"
    blocks = _mermaid(text)
    assert blocks, f"{name}: no mermaid block"
    for body in blocks:
        assert body.startswith(("flowchart TD", "sequenceDiagram")), body[:30]


def test_expected_diagram_kinds() -> None:
    kinds = [b.split("\n")[0] for b in _mermaid(FLOW.read_text(encoding="utf-8"))]
    assert kinds == ["flowchart TD", "sequenceDiagram"]
    assert [b.split("\n")[0] for b in _mermaid(_readme_section())] == ["flowchart TD"]


NODE_LABEL_RE = re.compile(r"(\[\[|\(\[|\[|\{|\()([^\]\)\}]*?)(\]\]|\]\)|\]|\}|\))")


@pytest.mark.parametrize("name", ["docs/user-flow.md", "README.md#Cómo funciona"])
def test_flowchart_labels_have_no_breaking_characters(name: str) -> None:
    for body in _mermaid(_sources()[name]):
        if not body.startswith("flowchart"):
            continue
        for line in body.splitlines()[1:]:
            for _, label, _ in NODE_LABEL_RE.findall(line):
                assert not re.search(r"[\"'`(){}\[\]<>|;#]", label), f"{name}: {label!r}"
            # Every opener has its closer (no stray brackets in labels).
            stripped = re.sub(r"\|[^|]*\|", "", line)  # edge labels
            assert stripped.count("[") == stripped.count("]"), line
            assert stripped.count("{") == stripped.count("}"), line
            assert stripped.count("(") == stripped.count(")"), line
            assert '"' not in line and ";" not in line, line


def test_sequence_lines_have_no_breaking_characters() -> None:
    seq = next(b for b in _mermaid(FLOW.read_text(encoding="utf-8")) if b.startswith("seq"))
    in_alt = 0
    for line in seq.splitlines()[1:]:
        s = line.strip()
        assert ";" not in s and "#" not in s and '"' not in s, s
        if s.startswith("alt "):
            in_alt += 1
        elif s == "end":
            in_alt -= 1
        else:
            assert (
                s.startswith("participant ")
                or re.match(r"\w+-{1,2}>>?\w+: .+", s)
                or (s.startswith("alt "))
            ), f"unexpected sequence line: {s!r}"
    assert in_alt == 0, "alt block not closed"


# (2) Tools


def test_openapi_operation_ids_equal_tool_names() -> None:
    spec = json.loads(OPENAPI.read_text(encoding="utf-8"))
    ops = {op["operationId"] for path in spec["paths"].values() for op in path.values()}
    assert ops == set(TOOL_NAMES)


@pytest.mark.parametrize("name", ["docs/user-flow.md", "README.md#Cómo funciona"])
def test_flowchart_cites_exactly_the_four_tools(name: str) -> None:
    flow = next(b for b in _mermaid(_sources()[name]) if b.startswith("flow"))
    cited = set(TOOL_RE.findall(flow))
    assert cited == set(TOOL_NAMES), f"doc {sorted(cited)} vs real {sorted(TOOL_NAMES)}"


def test_tool_column_only_names_real_tools() -> None:
    text = FLOW.read_text(encoding="utf-8")
    cited: set[str] = set()
    for row in _table_rows(text):
        cited |= set(re.findall(r"`(\w+)`", row[1]))
    assert cited == set(TOOL_NAMES), f"doc {sorted(cited)} vs real {sorted(TOOL_NAMES)}"
    seq = next(b for b in _mermaid(text) if b.startswith("seq"))
    spec = json.loads(OPENAPI.read_text(encoding="utf-8"))
    ops = {p.lstrip("/"): o["operationId"] for p, v in spec["paths"].items() for o in v.values()}
    for endpoint in re.findall(r"POST /(\w+) con X-API-Key", seq):
        assert ops[endpoint] in TOOL_NAMES


# (3) RF-xx and EV-xx


@pytest.mark.parametrize("name", ["docs/user-flow.md", "README.md#Cómo funciona"])
def test_cited_ids_exist(name: str) -> None:
    text = _sources()[name]
    reqs = _req_text()
    full_reqs = REQS.read_text(encoding="utf-8")
    cases = _cases()
    for rf in set(re.findall(r"\bRF-\d{2}\b", text)):
        assert rf in reqs, f"{name}: {rf} not in requirements.md"
    for rn in set(re.findall(r"\b(?:RN|HU)-\d{2}\b", text)):
        assert re.search(rf"\*\*{rn}\b", full_reqs), f"{name}: {rn} not in requirements.md"
    for ev in set(re.findall(r"\bEV-\d{2}\b", text)):
        assert ev in cases, f"{name}: {ev} not in cases.csv"


def test_rf_text_matches_step() -> None:
    reqs = _req_text()
    text = FLOW.read_text(encoding="utf-8")
    for row in _table_rows(text):
        for rf in re.findall(r"RF-\d{2}", row[2]):
            assert RF_KEYWORDS[rf].lower() in reqs[rf].lower(), (
                f"step {row[0]!r} cites {rf}; requirement text is {reqs[rf]!r}"
            )


def test_ev_kind_matches_step() -> None:
    cases = _cases()
    seen = 0
    for row in _table_rows(FLOW.read_text(encoding="utf-8")):
        evs = re.findall(r"EV-\d{2}", row[3])
        if not evs:
            assert row[3].startswith("sin caso"), row
            continue
        expected = next(k for p, k in ROW_KINDS.items() if row[0].startswith(p))
        for ev in evs:
            kind = cases[ev]["esperado"].split(":")[0]
            assert kind in KINDS
            assert kind in expected, f"{row[0]!r}: {ev} is {kind}, doc implies {expected}"
            seen += 1
    assert seen >= 15


def test_rows_without_case_really_have_no_case() -> None:
    """'sin caso en cases.csv' must be true: no case about status, humans or metrics."""
    for row in _cases().values():
        assert not re.search(r"RF-(08|09|19)\b", row["intencion"] + row["notas"]), row["id"]


# (4) Numbers


def test_sla_and_priorities_match_config() -> None:
    sla = _config()["sla_horas"]
    assert sla == {"P1": 4, "P2": 8, "P3": 24, "P4": 72}
    text = FLOW.read_text(encoding="utf-8")
    for body in _mermaid(text):
        for prio in re.findall(r"\bP\d\b", body):
            assert prio in sla
    assert f"P1, SLA {sla['P1']} h" in text
    for ex in _json_examples(text):
        if "prioridad" in ex:
            assert ex["prioridad"] in sla
            assert ex["sla_horas"] == sla[ex["prioridad"]]
            opened = datetime.fromisoformat(ex["fecha_apertura"])
            due = datetime.fromisoformat(ex["fecha_limite_sla"])
            assert (due - opened).total_seconds() == ex["sla_horas"] * 3600


def test_examples_respect_threshold_and_statuses() -> None:
    cfg = _config()["retrieval"]
    threshold = cfg["similarity_threshold"]
    assert cfg["escalation_margin"] < threshold
    statuses = {"answered", "no_evidence", "mandatory_escalation"}
    text = FLOW.read_text(encoding="utf-8")
    for ex in _json_examples(text):
        if "status" in ex:
            assert ex["status"] in statuses
            if ex["status"] == "answered":
                assert all(c["similarity"] >= threshold for c in ex["citations"])
                assert ex["citations"], "answered without citation"
            if ex["status"] == "no_evidence":
                assert ex["citations"] == []
                assert ex["text"] == NO_EVIDENCE["es"], "doc vs real no_evidence text"
    for number, label in re.findall(r"(0[.,]\d+)\s*(?:de\s+)?(umbral|margen)", text, re.I):
        key = "similarity_threshold" if label.lower() == "umbral" else "escalation_margin"
        assert float(number.replace(",", ".")) == cfg[key]


# (5) Synthetic data note


def test_synthetic_note_present() -> None:
    assert NOTE in FLOW.read_text(encoding="utf-8")
    assert "Banco Altiplano" in FLOW.read_text(encoding="utf-8")


# (6) Real examples


def test_ticket_ids_and_articles() -> None:
    text = FLOW.read_text(encoding="utf-8")
    examples = _json_examples(text)
    ids = [ex["ticket_id"] for ex in examples if "ticket_id" in ex]
    assert len(ids) == 2
    for ticket_id in ids:
        assert re.fullmatch(r"TCK-\d{6}", ticket_id), ticket_id
    titles: dict[str, str] = {}
    for path in KB_DIR.glob("KB-*.md"):
        head = path.read_text(encoding="utf-8")
        art = re.search(r"^id: (KB-\d+)$", head, re.M)
        title = re.search(r"^titulo: (.+)$", head, re.M)
        assert art and title
        titles[art.group(1)] = title.group(1).strip()
    for kb in set(re.findall(r"\bKB-\d{3}\b", text)):
        assert kb in titles, f"{kb} not in data/knowledge_base"
    for ex in examples:
        for cit in ex.get("citations", []):
            assert titles[cit["article_id"]] == cit["titulo"], "doc vs real title"


def test_example_questions_are_the_real_eval_cases() -> None:
    cases = _cases()
    text = FLOW.read_text(encoding="utf-8")
    assert cases["EV-02"]["pregunta"].rstrip(".") in text
    # The doc quotes EV-03 without the inner quotes around Invalid key (cosmetic).
    ev03 = cases["EV-03"]["pregunta"].replace("'", "").rstrip(".")
    assert ev03 in text.replace("'", "").replace('"', "")
    assert "robot de conciliación RPA" in cases["EV-15"]["pregunta"]
    assert "robot de conciliación RPA" in text


SECRET_RES = [
    r"sk-[A-Za-z0-9_-]{16,}",
    r"AKIA[0-9A-Z]{12,}",
    r"AIza[0-9A-Za-z_-]{20,}",
    r"gh[pous]_[A-Za-z0-9]{20,}",
    r"Bearer\s+[A-Za-z0-9._-]{12,}",
    r"X-API-Key:\s*(?!<clave>)[^\s\"'\\]+",
    r"(?i)(api[_-]?key|secret|password|token)\s*[=:]\s*[\"']?[A-Za-z0-9]{12,}",
]


@pytest.mark.parametrize("name", ["docs/user-flow.md", "README.md#Cómo funciona"])
def test_no_secrets(name: str) -> None:
    text = _sources()[name]
    for pattern in SECRET_RES:
        assert not re.search(pattern, text), f"{name}: secret-like text for {pattern}"


# (7) Links


def test_relative_links_resolve() -> None:
    for name, base in (
        ("docs/user-flow.md", FLOW.parent),
        ("README.md#Cómo funciona", README.parent),
    ):
        text = re.sub(BLOCK_RE, "", _sources()[name])
        links = [t for t in LINK_RE.findall(text) if not t.startswith(("http", "#", "mailto"))]
        assert links, name
        for target in links:
            path = (base / target.split("#")[0]).resolve()
            assert path.exists(), f"{name}: broken link {target}"
            assert Path(path).is_relative_to(PROJECT_ROOT)
