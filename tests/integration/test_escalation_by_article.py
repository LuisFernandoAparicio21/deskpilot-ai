"""RN-03 by retrieved article: a cash query with no regex keyword escalates through KB-011."""

from __future__ import annotations

from pathlib import Path

import pytest

from src.llm import NoLLM
from src.retrieval import AnswerService, escalation_reason
from src.utils.config import Settings, load_settings
from tests.unit.test_answer_service import FakeLLM, _ScoredRetriever

QUERY = "se congela la terminal con billetes en ventanilla"


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return load_settings(env_file=tmp_path / "missing.env")


def test_query_has_no_regex_keyword() -> None:
    assert escalation_reason(QUERY) is None


def test_kb011_top1_gives_mandatory_escalation_by_article(settings: Settings) -> None:
    llm = FakeLLM("1. Reinicia la terminal.")
    answer = AnswerService(
        _ScoredRetriever({"KB-011": 0.8, "KB-002": 0.4}),  # type: ignore[arg-type]
        llm,
        settings,
    ).answer(QUERY)
    assert answer.status == "mandatory_escalation"
    assert answer.mode == "policy"
    assert [c.article_id for c in answer.citations] == ["KB-011"]
    assert "Reinicia" not in answer.text and "Detén" not in answer.text
    assert llm.calls == []


def test_same_query_without_kb011_on_top_is_not_escalated(settings: Settings) -> None:
    answer = AnswerService(
        _ScoredRetriever({"KB-002": 0.8, "KB-011": 0.4}),  # type: ignore[arg-type]
        NoLLM(),
        settings,
    ).answer(QUERY)
    assert answer.status != "mandatory_escalation"
