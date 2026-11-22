"""RN-03: cases that are always escalated to a human, without trying to solve them.

Fraud, suspected unauthorized access and cash-system failures are detected by keyword
patterns in the (redacted) query or by the retrieved article: KB-011 (sistema de caja)
says it is always escalated. Matching ignores case and accents. Patterns are narrow on
purpose; a miss still goes through retrieval, where KB-011 and the "Cuándo escalar"
sections repeat the rule.
"""

from __future__ import annotations

import re
import unicodedata
from typing import Literal

EscalationReason = Literal["fraud", "unauthorized_access", "cash_system", "article"]

# Articles whose content must never be turned into self-service steps.
MANDATORY_ESCALATION_ARTICLES = frozenset({"KB-011"})

_PATTERNS: dict[EscalationReason, re.Pattern[str]] = {
    "fraud": re.compile(
        r"\bfraud|\bestafa|\bscam\b|\bclonaron\b|\bskimm"
        r"|\boperacion(?:es)? no autorizada|\bunauthori[sz]ed (?:transaction|operation|charge)"
    ),
    "unauthorized_access": re.compile(
        r"\baccesos? no autorizados?|\bunauthori[sz]ed access"
        r"|\baccesos? que no reconozco|\bno reconozco (?:los |estos |esos )?accesos"
        r"|\balguien (?:mas )?(?:entro|accedio|uso|usa|esta usando) (?:a )?mi"
        r"|\bentraron (?:a|en) mi|\bhackea|\bhackeo\b|\bhacked\b"
        r"|\bsomeone (?:else )?(?:logged|accessed|used|is using)"
        r"|\bcuenta comprometida|\bcompromised account|\baccount (?:was |is )?compromised"
        r"|\bcambio de contrasena que no solicite|\bpassword change i didn.?t request"
    ),
    "cash_system": re.compile(
        r"\b(?:sistema|terminal|equipo|modulo|software|pantalla) de (?:la )?caja\b"
        r"|\bla caja (?:no|se)\b|\bcash (?:register|system)|\bteller (?:system|terminal)"
    ),
}


def _normalize(text: str) -> str:
    ascii_text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    return ascii_text.lower()


def escalation_reason(query: str) -> EscalationReason | None:
    """Why ``query`` must be escalated (RN-03), or None."""
    normalized = _normalize(query)
    for reason, pattern in _PATTERNS.items():
        if pattern.search(normalized):
            return reason
    return None
