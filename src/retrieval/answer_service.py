"""Cited answer for a user query: the core of ``buscar_solucion`` (S7, RF-04, RF-05, RF-14).

Order of decisions, each one final:

1. Redact sensitive data (RF-10, RN-05). From here on only the redacted query is used
   (retrieval, LLM); logs never get the query text, only its length and the outcome.
2. Detect the language (RF-01, HU-04) and retrieve articles (RF-12, RF-13).
3. RN-03: fraud, suspected unauthorized access or cash-system failure (keywords, or the
   any evidence article is KB-011) => ``mandatory_escalation`` with no steps.
4. No article reaches the threshold => ``no_evidence`` with the fixed message (RF-05).
5. Evidence => with ``NoLLM`` the extractive answer: the "Pasos" section of the top
   article plus "Fuente: <id> — <título>". With an LLM, ``answer_with_citation@v1`` over
   the retrieved context; if the LLM fails or times out, the extractive answer is used
   and a warning is logged (RNF-06). The same fallback applies when the LLM output cites a
   ``KB-<n>`` id that is not in the evidence (invented source) or contains sensitive data
   (RF-10). Every answer with steps cites its article (RN-04).

Known limitation: in extractive mode an English query gets English framing and the same
cited article, but the steps are quoted in Spanish as written in the knowledge base. In
Copilot Studio the generative orchestrator presents them in the user's language.
"""

from __future__ import annotations

import logging
import re
from collections.abc import Mapping
from typing import TYPE_CHECKING, Literal

from pydantic import BaseModel, ConfigDict, Field

from src.llm import LLMClient, LLMError, NoLLM
from src.prompts import (
    EXTRACTIVE_INTRO,
    MANDATORY_ESCALATION,
    NO_EVIDENCE,
    NO_EVIDENCE_TOKEN,
    SENSITIVE_DATA_WARNING,
    ContextArticle,
    Language,
    build_answer_prompt,
    message,
    source_line,
)
from src.retrieval.language import detect_language
from src.retrieval.policy import MANDATORY_ESCALATION_ARTICLES, escalation_reason
from src.retrieval.retriever import ArticleHit, RetrievalResult, Retriever, chunk_body
from src.utils.redaction import contains_sensitive, redact

if TYPE_CHECKING:
    from src.utils.config import Settings

logger = logging.getLogger(__name__)

STEPS_SECTION = "pasos"
AnswerStatus = Literal["answered", "no_evidence", "mandatory_escalation"]
AnswerMode = Literal["extractive", "llm", "policy"]

_NUMBERED = re.compile(r"^\d+[.)]\s+(?P<step>.+)$")
_ARTICLE_ID = re.compile(r"KB-\d+")
_BULLET = re.compile(r"^[-*•]\s+(?P<step>.+)$")


class Citation(BaseModel):
    model_config = ConfigDict(frozen=True)

    article_id: str
    titulo: str
    seccion: str
    similarity: float = Field(ge=0.0, le=1.0)


class Answer(BaseModel):
    """What ``buscar_solucion`` returns; ``text`` is ready to show to the user."""

    model_config = ConfigDict(frozen=True)

    status: AnswerStatus
    language: Language
    text: str
    citations: list[Citation]
    sensitive_data_warning: bool
    mode: AnswerMode
    prompt_key: str | None = None


def format_steps(text: str) -> list[str]:
    """Steps of a "Pasos" section: numbered or bulleted lines; loose lines join the last step."""
    steps: list[str] = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        match = _NUMBERED.match(line) or _BULLET.match(line)
        if match:
            steps.append(match.group("step").strip())
        elif steps:
            steps[-1] = f"{steps[-1]} {line}"
        else:
            steps.append(line)
    return steps


def _citation(article: ArticleHit) -> Citation:
    return Citation(
        article_id=article.article_id,
        titulo=article.titulo,
        seccion=article.best_section,
        similarity=round(article.score, 4),
    )


class AnswerService:
    """Turns a query into an ``Answer`` with retrieval, policy and an optional LLM."""

    def __init__(self, retriever: Retriever, llm: LLMClient, settings: Settings) -> None:
        self._retriever = retriever
        self._llm = llm
        self._timeout_s = settings.llm.timeout_s

    def answer(self, query: str, categoria: str | None = None) -> Answer:
        if not query.strip():
            raise ValueError("query must not be empty")
        sensitive = bool(contains_sensitive(query))
        safe_query = redact(query) if sensitive else query
        language = detect_language(safe_query)
        result = self._retriever.search(safe_query, categoria)
        answer = self._decide(safe_query, language, result, sensitive)
        top = result.top
        logger.info(
            "Answer produced",
            extra={
                "status": answer.status,
                "mode": answer.mode,
                "language": language,
                "query_chars": len(query),
                "sensitive_data": sensitive,
                "top_article": top.article_id if top else None,
                "top_score": round(top.score, 3) if top else None,
                "threshold": result.threshold,
                "categoria": categoria,
            },
        )
        return answer

    # --- decisions -------------------------------------------------------------------

    def _decide(
        self, query: str, language: Language, result: RetrievalResult, sensitive: bool
    ) -> Answer:
        evidence = result.evidence
        top = evidence[0] if evidence else None
        mandatory = [a for a in evidence if a.article_id in MANDATORY_ESCALATION_ARTICLES]
        reason = escalation_reason(query) or ("article" if mandatory else None)
        if reason is not None:
            logger.info("Mandatory escalation (RN-03)", extra={"reason": reason})
            cited = mandatory[:1]
            return self._fixed(
                MANDATORY_ESCALATION, "mandatory_escalation", language, sensitive, cited
            )
        if top is None:
            return self._fixed(NO_EVIDENCE, "no_evidence", language, sensitive, [])
        if not isinstance(self._llm, NoLLM):
            generated = self._with_llm(query, language, result, sensitive)
            if generated is not None:
                return generated
        return self._extractive(language, result, top, sensitive)

    def _fixed(
        self,
        table: Mapping[Language, str],
        status: AnswerStatus,
        language: Language,
        sensitive: bool,
        cited: list[ArticleHit],
    ) -> Answer:
        text = message(table, language)
        return Answer(
            status=status,
            language=language,
            text=self._with_warning(text, language, sensitive),
            citations=[_citation(article) for article in cited],
            sensitive_data_warning=sensitive,
            mode="policy",
        )

    @staticmethod
    def _with_warning(text: str, language: Language, sensitive: bool) -> str:
        if not sensitive:
            return text
        return f"{message(SENSITIVE_DATA_WARNING, language)}\n\n{text}"

    # --- extractive ------------------------------------------------------------------

    def _steps_text(self, result: RetrievalResult, top: ArticleHit) -> str:
        """The "Pasos" section of ``top``; falls back to its best retrieved chunk."""
        section = self._retriever.section_text(top.article_id, STEPS_SECTION, result.query_vector)
        return section if section else chunk_body(top.chunks[0].chunk.text)

    def _extractive(
        self, language: Language, result: RetrievalResult, top: ArticleHit, sensitive: bool
    ) -> Answer:
        steps = format_steps(self._steps_text(result, top))
        lines = [message(EXTRACTIVE_INTRO, language, article_id=top.article_id, titulo=top.titulo)]
        lines += [f"{n}. {step}" for n, step in enumerate(steps, start=1)]
        text = "\n".join(lines) + "\n\n" + source_line(language, top.article_id, top.titulo)
        return Answer(
            status="answered",
            language=language,
            text=self._with_warning(text, language, sensitive),
            citations=[_citation(top)],
            sensitive_data_warning=sensitive,
            mode="extractive",
        )

    # --- LLM -------------------------------------------------------------------------

    def _context(self, result: RetrievalResult) -> list[ContextArticle]:
        context: list[ContextArticle] = []
        for article in result.evidence:
            for scored in article.chunks:
                meta = scored.chunk.metadata
                context.append(
                    ContextArticle(
                        article_id=article.article_id,
                        titulo=article.titulo,
                        seccion=meta.seccion,
                        similarity=scored.similarity,
                        text=chunk_body(scored.chunk.text),
                    )
                )
        top = result.evidence[0]
        if not any(c.article_id == top.article_id and c.seccion == STEPS_SECTION for c in context):
            steps = self._retriever.section_text(top.article_id, STEPS_SECTION, result.query_vector)
            if steps:
                context.insert(
                    0,
                    ContextArticle(
                        article_id=top.article_id,
                        titulo=top.titulo,
                        seccion=STEPS_SECTION,
                        similarity=top.score,
                        text=steps,
                    ),
                )
        return context

    def _with_llm(
        self, query: str, language: Language, result: RetrievalResult, sensitive: bool
    ) -> Answer | None:
        prompt = build_answer_prompt(query, self._context(result), language)
        try:
            text = self._llm.generate(prompt.system, prompt.user, self._timeout_s)
        except LLMError as exc:
            logger.warning(
                "LLM failed; using the extractive answer",
                extra={"provider": self._llm.provider, "error": type(exc).__name__},
            )
            return None
        if NO_EVIDENCE_TOKEN in text:
            answer = self._fixed(NO_EVIDENCE, "no_evidence", language, sensitive, [])
            return answer.model_copy(update={"mode": "llm", "prompt_key": prompt.key})
        evidence = result.evidence
        evidence_ids = {article.article_id for article in evidence}
        cited_ids = set(_ARTICLE_ID.findall(text))
        if cited_ids - evidence_ids:
            logger.warning(
                "LLM cited an article outside the evidence; using the extractive answer",
                extra={
                    "provider": self._llm.provider,
                    "unknown_ids": len(cited_ids - evidence_ids),
                },
            )
            return None
        if contains_sensitive(text):
            logger.warning(
                "LLM output contains sensitive data; using the extractive answer",
                extra={"provider": self._llm.provider},
            )
            return None
        cited = [article for article in evidence if article.article_id in cited_ids]
        if not cited:
            cited = [evidence[0]]
            text = f"{text}\n\n{source_line(language, evidence[0].article_id, evidence[0].titulo)}"
        return Answer(
            status="answered",
            language=language,
            text=self._with_warning(text, language, sensitive),
            citations=[_citation(article) for article in cited],
            sensitive_data_warning=sensitive,
            mode="llm",
            prompt_key=prompt.key,
        )
