"""Fixed user-facing messages in Spanish and English (RF-01, RF-05, RF-10, RN-03).

These texts never go through an LLM, so they are identical in extractive and LLM
mode. Spanish is neutral Mexican Spanish (RNF-12).
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Literal

Language = Literal["es", "en"]

# RF-05: no evidence => say so explicitly, never invent steps, and offer a ticket.
NO_EVIDENCE: Mapping[Language, str] = {
    "es": (
        "No lo sé, escalo a un agente humano. No encontré un artículo de la base de "
        "conocimiento con evidencia suficiente para tu caso. ¿Quieres que cree un ticket?"
    ),
    "en": (
        "I don't know, I'm escalating to a human agent. I couldn't find a knowledge-base "
        "article with enough evidence for your case. Do you want me to create a ticket?"
    ),
}

# RN-03: fraud, suspected unauthorized access and cash-system failures always escalate.
MANDATORY_ESCALATION: Mapping[Language, str] = {
    "es": (
        "Este caso se escala siempre a un agente humano (fraude, sospecha de acceso no "
        "autorizado o falla en el sistema de caja). No intentes resolverlo por tu cuenta: "
        "voy a crear un ticket para el equipo especializado."
    ),
    "en": (
        "This case is always escalated to a human agent (fraud, suspected unauthorized "
        "access or a cash-system failure). Please don't try to fix it yourself: I'll "
        "create a ticket for the specialized team."
    ),
}

# RF-10 / RN-05: warn and do not keep the sensitive value.
SENSITIVE_DATA_WARNING: Mapping[Language, str] = {
    "es": (
        "Importante: no compartas contraseñas, NIP, tokens, números de tarjeta ni CURP, "
        "ni siquiera con soporte. Quité esos datos de tu mensaje y no se guardan."
    ),
    "en": (
        "Important: never share passwords, PINs, tokens, card numbers or CURP, not even "
        "with support. I removed that data from your message and it is not stored."
    ),
}

# Extractive mode (no LLM). The knowledge base is written in Spanish, so in English the
# framing explains that the quoted steps stay in Spanish (known limitation, see README).
EXTRACTIVE_INTRO: Mapping[Language, str] = {
    "es": "Sigue estos pasos del artículo {article_id} — {titulo}:",
    "en": (
        "Follow these steps from article {article_id} — {titulo} "
        "(the knowledge base is in Spanish, so the steps are quoted as written):"
    ),
}

SOURCE_LABEL: Mapping[Language, str] = {"es": "Fuente", "en": "Source"}

LANGUAGE_NAMES: Mapping[Language, str] = {"es": "español neutro de México", "en": "English"}


def message(table: Mapping[Language, str], language: Language, **values: str) -> str:
    """Text of ``table`` in ``language``, with ``{placeholders}`` filled from ``values``."""
    text = table[language]
    return text.format(**values) if values else text


def source_line(language: Language, article_id: str, titulo: str) -> str:
    """``"Fuente: KB-002 — <título>"`` (RF-04: ID and title of the source article)."""
    return f"{SOURCE_LABEL[language]}: {article_id} — {titulo}"
