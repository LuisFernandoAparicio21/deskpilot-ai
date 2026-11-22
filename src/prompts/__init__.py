"""Versioned prompt templates (cited answer, ticket classification) and fixed messages."""

from src.prompts.messages import (
    EXTRACTIVE_INTRO,
    LANGUAGE_NAMES,
    MANDATORY_ESCALATION,
    NO_EVIDENCE,
    SENSITIVE_DATA_WARNING,
    SOURCE_LABEL,
    Language,
    message,
    source_line,
)
from src.prompts.templates import (
    ANSWER_WITH_CITATION,
    NO_EVIDENCE_TOKEN,
    PROMPTS,
    TICKET_CLASSIFICATION,
    ContextArticle,
    PromptTemplate,
    RenderedPrompt,
    build_answer_prompt,
    build_classification_prompt,
    escape_untrusted,
    get_prompt,
)

__all__ = [
    "ANSWER_WITH_CITATION",
    "EXTRACTIVE_INTRO",
    "LANGUAGE_NAMES",
    "MANDATORY_ESCALATION",
    "NO_EVIDENCE",
    "NO_EVIDENCE_TOKEN",
    "PROMPTS",
    "SENSITIVE_DATA_WARNING",
    "SOURCE_LABEL",
    "TICKET_CLASSIFICATION",
    "ContextArticle",
    "Language",
    "PromptTemplate",
    "RenderedPrompt",
    "build_answer_prompt",
    "build_classification_prompt",
    "escape_untrusted",
    "get_prompt",
    "message",
    "source_line",
]
