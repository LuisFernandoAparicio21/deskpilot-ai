"""Category and priority of a new ticket: deterministic rules, optional LLM (S9, RF-16).

``classify`` works on the *redacted* description only (RN-05). The rules are the default
and the fallback:

- RN-03: fraud, suspected unauthorized access or a cash-system failure (``policy``) is
  always priority P1 and marked as escalated, whatever the LLM says.
- RN-01: P1 affects a whole branch or customer operations, P2 a user who cannot work,
  P3 a degradation with a workaround, P4 a request or a question (the default).

With an LLM (``ticket_classification@v1``) its output is never trusted: it must be one JSON
object, ``categoria`` must be in ``KNOWN_CATEGORIES`` and ``prioridad`` in P1-P4. A priority
is accepted only when it is at most one level away from the rules, and P1 only when the
rules say P1 (a prompt-injected ticket cannot jump the queue). Any failure falls back to
the rules. The free-text reason of the model is discarded.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from typing import Any, Literal

from src.llm import LLMClient, LLMError
from src.prompts import build_classification_prompt
from src.retrieval.answer_service import KNOWN_CATEGORIES
from src.retrieval.policy import EscalationReason, escalation_reason, normalize_text

logger = logging.getLogger(__name__)

Priority = Literal["P1", "P2", "P3", "P4"]
ClassificationMode = Literal["rules", "llm"]
PRIORITIES: tuple[Priority, ...] = ("P1", "P2", "P3", "P4")
DEFAULT_CATEGORY = "General"
DEFAULT_SUBCATEGORY = "Consulta general"
OTHER_SUBCATEGORY = "Otros"
_MAX_LLM_JSON_CHARS = 2000

# (subcategory, category, pattern on accent-free lower case text); the first match wins.
_SUBCATEGORY_RULES: tuple[tuple[str, str, re.Pattern[str]], ...] = tuple(
    (name, category, re.compile(pattern))
    for name, category, pattern in (
        ("Desbloqueo de usuario", "Accesos", r"bloquead|\blocked|desbloque|unlock"),
        ("Reseteo de contrasena", "Accesos", r"contrasena|password|olvide mi clave"),
        ("Token bancario", "Accesos", r"\btoken"),
        ("VPN", "Conectividad", r"\bvpn\b"),
        ("Impresoras", "Hardware", r"impresora|impresion|imprimir|printer|\bprint"),
        ("Acceso a SAP", "Accesos", r"\bsap\b"),
        ("Acceso a core bancario", "Accesos", r"core bancario|core banking"),
        ("Carpetas compartidas", "Conectividad", r"carpetas? compartid|shared (?:folder|drive)"),
        (
            "Equipo lento",
            "Hardware",
            r"(?:equipo|computadora|laptop|pc)\s+(?:muy\s+)?lent|(?:slow|sluggish)\s+"
            r"(?:computer|pc|laptop)|(?:computer|pc|laptop)\s+is\s+(?:very\s+)?slow",
        ),
        ("Escaner de cheques", "Hardware", r"escaner|scanner"),
        ("Correo", "Comunicaciones", r"correo|e-?mail|outlook"),
        ("Microsoft Teams", "Comunicaciones", r"\bteams\b"),
        ("Telefonia", "Comunicaciones", r"telefon|extension|\bphone"),
        ("Instalacion de software", "Software", r"instal|\binstall"),
        (
            "Alta de usuario",
            "Accesos",
            r"alta de usuario|nuevo empleado|new (?:hire|employee)|(?:crear|create) usuario",
        ),
        (
            "Red de sucursal",
            "Conectividad",
            r"sin (?:internet|red)\b|no hay (?:internet|red)\b|\bwi-?fi\b|red de (?:la )?sucursal"
            r"|(?:network|internet) (?:is |went )?(?:down|outage)|internet caid"
            r"|\bno (?:internet|network)\b|(?:lost|losing|lack of) (?:the )?(?:internet|network)"
            r"|branch (?:network|internet)|(?:network|internet) (?:at|of|in) the branch"
            r"|(?:internet|network) (?:is )?(?:not working|out)\b",
        ),
        (
            "Equipo danado",
            "Hardware",
            r"danad|\broto\b|\brota\b|broken|damaged|no enciende|won.?t turn on",
        ),
    )
)

_ESCALATED: dict[EscalationReason, tuple[str, str]] = {
    "fraud": ("Sospecha de fraude", DEFAULT_CATEGORY),
    "unauthorized_access": ("Acceso no autorizado", "Accesos"),
    "cash_system": ("Sistema de caja", "Hardware"),
    "article": ("Sistema de caja", "Hardware"),
}

_P1 = re.compile(
    r"toda la sucursal|sucursal (?:completa|entera|sin)|todos? (?:los )?(?:usuarios|equipos|cajas)"
    r" de (?:la )?sucursal|clientes? (?:no|sin)\b|no (?:podemos|se puede) (?:atender|operar)"
    r"|(?:whole|entire|all of the) branch|branch is down|cannot serve (?:the )?customers"
    r"|everyone (?:in|at) the branch"
)
_P2 = re.compile(
    r"no puedo (?:entrar|ingresar|acceder|iniciar|trabajar|operar|abrir|conectar|usar)"
    r"|no me deja (?:entrar|ingresar|acceder|iniciar)|sin acceso|no tengo acceso|bloquead"
    r"|can.?t (?:log|sign|access|work|connect|use)|cannot (?:log|sign|access|work|connect|use)"
    r"|unable to (?:work|log|sign|access|connect)|locked out|\blocked\b"
)
_P3 = re.compile(
    r"\blent[oa]|\bslow|intermitente|intermittent|a veces|sometimes|se cae\b|se desconecta"
    r"|keeps? (?:dropping|disconnecting)|degrad|tarda|takes (?:a long|too long)"
)


@dataclass(frozen=True)
class Classification:
    """Outcome of ``classify``: what is stored and returned for the ticket."""

    categoria: str
    subcategoria: str
    prioridad: Priority
    escalation: EscalationReason | None
    mode: ClassificationMode

    @property
    def escalated(self) -> bool:
        return self.escalation is not None


def _rule_priority(text: str) -> Priority:
    if _P1.search(text):
        return "P1"
    if _P2.search(text):
        return "P2"
    if _P3.search(text):
        return "P3"
    return "P4"


def classify_by_rules(description: str) -> Classification:
    """Deterministic classification of an already redacted ``description``."""
    reason = escalation_reason(description)
    if reason is not None:
        subcategory, category = _ESCALATED[reason]
        return Classification(category, subcategory, "P1", reason, "rules")
    text = normalize_text(description)
    subcategory, category = DEFAULT_SUBCATEGORY, DEFAULT_CATEGORY
    for name, rule_category, pattern in _SUBCATEGORY_RULES:
        if pattern.search(text):
            subcategory, category = name, rule_category
            break
    return Classification(category, subcategory, _rule_priority(text), None, "rules")


def _parse_llm_output(raw: str) -> tuple[str, Priority] | None:
    """``(categoria, prioridad)`` from the model output, or None if anything is off."""
    text = raw.strip()
    if len(text) > _MAX_LLM_JSON_CHARS:
        return None
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end < start:
        return None
    try:
        data: Any = json.loads(text[start : end + 1])
    except ValueError:
        return None
    if not isinstance(data, dict):
        return None
    categoria, prioridad = data.get("categoria"), data.get("prioridad")
    if not isinstance(categoria, str) or categoria not in KNOWN_CATEGORIES:
        return None
    if not isinstance(prioridad, str) or prioridad not in PRIORITIES:
        return None
    return categoria, prioridad


def _accept_priority(llm: Priority, rules: Priority) -> bool:
    if llm == "P1" and rules != "P1":
        return False
    return abs(PRIORITIES.index(llm) - PRIORITIES.index(rules)) <= 1


def classify(description: str, llm: LLMClient, timeout_s: float) -> Classification:
    """Rules, refined by the LLM when one is configured; never raises for LLM failures."""
    base = classify_by_rules(description)
    if base.escalated or llm.provider == "none":
        return base
    prompt = build_classification_prompt(description, sorted(KNOWN_CATEGORIES))
    try:
        raw = llm.generate(prompt.system, prompt.user, timeout_s)
    except LLMError:
        logger.warning("Ticket classification fell back to rules", extra={"reason": "llm_error"})
        return base
    parsed = _parse_llm_output(raw)
    if parsed is None:
        logger.warning("Ticket classification fell back to rules", extra={"reason": "bad_output"})
        return base
    categoria, prioridad = parsed
    if not _accept_priority(prioridad, base.prioridad):
        logger.warning("LLM priority rejected", extra={"reason": "out_of_range"})
        prioridad = base.prioridad
    subcategory = base.subcategoria if categoria == base.categoria else OTHER_SUBCATEGORY
    return Classification(categoria, subcategory, prioridad, None, "llm")
