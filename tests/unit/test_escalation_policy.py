"""RN-03 keyword policy: cash-system and unauthorized-access patterns, with and without accents."""

from __future__ import annotations

from pathlib import Path

import pytest

from src.api.classification import classify, classify_by_rules
from src.llm import LLMError
from src.retrieval import escalation_reason
from src.utils.config import Settings
from tests.unit.conftest import FakeRepository, settings_with_key
from tests.unit.test_classification import FakeLLM
from tests.unit.test_ticket_service import NOW, TicketService, _request

CASH_SYSTEM = [
    "la caja registradora no abre",
    "teller down",
    "POS offline",
    "la caja esta caida",
    "la caja está caída",
    "nadie puede cobrar en ventanilla",
    "nobody can take payments",
]
UNAUTHORIZED = [
    "alguien robo mi cuenta",
    "alguien robó mi cuenta",
    "sospecho de un acceso indebido",
    "someone stole my account",
    "acceso indebido",
]
NEGATIVES = [
    "la impresora de la caja de ahorro",
    "no puedo iniciar sesión",
    "mi sesión expiró",
    "I can't log in",
    "cuenta de ahorro",
    "printer down",
]
POSITIVES = [(t, "cash_system") for t in CASH_SYSTEM] + [
    (t, "unauthorized_access") for t in UNAUTHORIZED
]


@pytest.mark.parametrize(("text", "reason"), POSITIVES)
def test_positive_phrases_give_the_expected_reason(text: str, reason: str) -> None:
    assert escalation_reason(text) == reason


@pytest.mark.parametrize("text", NEGATIVES)
def test_negative_phrases_are_not_escalated(text: str) -> None:
    assert escalation_reason(text) is None


@pytest.mark.parametrize(("text", "reason"), POSITIVES)
def test_rules_classification_is_p1_and_escalated(text: str, reason: str) -> None:
    result = classify_by_rules(text)
    assert (result.prioridad, result.escalation, result.escalated) == ("P1", reason, True)


@pytest.mark.parametrize(("text", "reason"), POSITIVES)
def test_classify_with_llm_never_consults_it_and_escalates(text: str, reason: str) -> None:
    llm = FakeLLM('{"categoria": "Accesos", "prioridad": "P4", "motivo": "x"}')
    result = classify(text, llm, 5.0)
    assert (result.prioridad, result.escalation) == ("P1", reason)
    assert llm.prompts == []


@pytest.mark.parametrize("text", NEGATIVES)
def test_negatives_are_not_p1_escalated_by_classify(text: str) -> None:
    result = classify_by_rules(text)
    assert result.escalation is None and not result.escalated


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return settings_with_key(tmp_path)


@pytest.mark.parametrize(("text", "reason"), POSITIVES)
def test_crear_ticket_service_creates_p1_escalated_ticket(
    settings: Settings, text: str, reason: str
) -> None:
    service = TicketService(
        FakeRepository(), FakeLLM(error=LLMError("off")), settings, clock=lambda: NOW
    )
    response = service.create(_request(text))
    assert response.prioridad == "P1"
    assert response.escalado is True
    assert response.motivo_escalamiento == reason
