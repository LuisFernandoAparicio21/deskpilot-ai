"""``TicketService``: redact first, classify, SLA, persist, log without text (S9, RN-01..05)."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from src.api.repository import NewTicket, RepositoryUnavailableError
from src.api.schemas import CrearTicketRequest
from src.api.ticket_service import TicketService
from src.llm import LLMError
from src.utils.config import Settings
from tests.unit.conftest import FakeRepository, settings_with_key
from tests.unit.test_classification import FakeLLM, _json

NOW = datetime(2026, 3, 2, 9, 30, 0)
# Synthetic secrets: none of these strings may reach the row, the response, logs or the LLM.
SECRETS = {
    "password": ("mi contraseña es Zx9secretoPW", "Zx9secretoPW"),
    "pin": ("mi NIP es 482193", "482193"),
    "card": ("la tarjeta 4539 1488 0343 6467 fue rechazada", "4539 1488 0343 6467"),
    "curp": ("mi CURP es HEGG560427MVZRRL04", "HEGG560427MVZRRL04"),
    "token": ("token: aB3xKq9ZpLm2Wv7Rt", "aB3xKq9ZpLm2Wv7Rt"),
}


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return settings_with_key(tmp_path)


def _service(
    settings: Settings, llm: FakeLLM | None = None
) -> tuple[TicketService, FakeRepository, FakeLLM]:
    repo = FakeRepository()
    fake = llm or FakeLLM(error=LLMError("off"))
    return TicketService(repo, fake, settings, clock=lambda: NOW), repo, fake


def _request(text: str, **kw: str) -> CrearTicketRequest:
    return CrearTicketRequest(
        descripcion=text, sucursal=kw.get("sucursal", "Centro"), area=kw.get("area", "Caja")
    )


@pytest.mark.parametrize(
    ("text", "priority", "hours"),
    [
        ("Toda la sucursal sin red", "P1", 4),
        ("No puedo entrar al sistema", "P2", 8),
        ("La VPN es intermitente", "P3", 24),
        ("Necesito instalar Adobe Reader", "P4", 72),
    ],
)
def test_sla_hours_follow_the_priority_and_the_deadline_is_opening_plus_sla(
    settings: Settings, text: str, priority: str, hours: int
) -> None:
    service, repo, _ = _service(settings)
    response = service.create(_request(text))
    assert (response.prioridad, response.sla_horas) == (priority, hours)
    assert response.fecha_apertura == NOW
    assert response.fecha_limite_sla == NOW + timedelta(hours=hours)
    assert repo.created[0].sla_horas == hours
    assert repo.created[0].prioridad == priority


def test_sla_hours_come_from_the_configuration(settings: Settings) -> None:
    custom = settings.model_copy(
        update={"sla_horas": settings.sla_horas.model_copy(update={"P4": 96})}
    )
    service, _, _ = _service(custom)
    assert service.create(_request("Necesito instalar Adobe Reader")).sla_horas == 96


@pytest.mark.parametrize(
    ("text", "reason"),
    [
        ("Veo cargos no reconocidos en una cuenta", "fraud"),
        ("Hay un acceso no autorizado a mi usuario", "unauthorized_access"),
        ("El sistema de caja no responde", "cash_system"),
    ],
)
def test_mandatory_escalation_is_p1_escalated_with_4h_and_never_asks_the_llm(
    settings: Settings, text: str, reason: str
) -> None:
    service, repo, llm = _service(settings, FakeLLM(reply=_json("Software", "P4")))
    response = service.create(_request(text))
    assert (response.prioridad, response.sla_horas) == ("P1", 4)
    assert response.escalado is True
    assert response.motivo_escalamiento == reason
    assert response.mode == "rules"
    assert llm.prompts == []
    assert repo.created[0].prioridad == "P1"


def test_non_escalated_ticket_has_no_escalation_reason(settings: Settings) -> None:
    response = _service(settings)[0].create(_request("La VPN es intermitente"))
    assert (response.escalado, response.motivo_escalamiento) == (False, None)


def test_response_mode_is_llm_when_the_model_answers_and_rules_when_it_fails(
    settings: Settings,
) -> None:
    ok, _, _ = _service(settings, FakeLLM(reply=_json("Software", "P3")))
    assert ok.create(_request("Necesito ayuda con un programa raro")).mode == "llm"
    bad, _, _ = _service(settings, FakeLLM(error=LLMError("down")))
    assert bad.create(_request("Necesito ayuda con un programa raro")).mode == "rules"


def test_stored_ticket_carries_the_request_fields_and_classification(settings: Settings) -> None:
    service, repo, _ = _service(settings)
    response = service.create(_request("La VPN es intermitente", sucursal="Norte", area="Ventas"))
    row = repo.created[0]
    assert (row.sucursal, row.area, row.canal) == ("Norte", "Ventas", "Teams")
    assert (row.categoria, row.subcategoria) == ("Conectividad", "VPN")
    assert row.idioma == "es"
    assert row.fecha_apertura == NOW
    assert response.ticket_id.startswith("TCK-")
    assert response.estado == "abierto"
    assert response.sensitive_data_warning is False


def test_english_description_is_stored_with_language_en(settings: Settings) -> None:
    service, repo, _ = _service(settings)
    service.create(_request("My laptop is very slow in the mornings"))
    assert repo.created[0].idioma == "en"


@pytest.mark.parametrize("kind", sorted(SECRETS))
def test_sensitive_value_never_reaches_row_response_logs_or_llm(
    settings: Settings, caplog: pytest.LogCaptureFixture, kind: str
) -> None:
    sentence, secret = SECRETS[kind]
    llm = FakeLLM(reply=_json("Accesos", "P3"))
    service, repo, _ = _service(settings, llm)
    with caplog.at_level(logging.DEBUG):
        response = service.create(_request(f"No puedo iniciar sesión, {sentence} gracias"))
    stored: NewTicket = repo.created[0]
    assert secret not in stored.descripcion
    assert "[REDACTED:" in stored.descripcion
    assert response.sensitive_data_warning is True
    assert secret not in response.model_dump_json()
    assert "descripcion" not in response.model_dump()
    assert len(llm.prompts) == 1
    assert secret not in " ".join(llm.prompts[0])
    logged = "\n".join(f"{r.getMessage()} {r.__dict__}" for r in caplog.records)
    assert secret not in logged
    assert "No puedo iniciar" not in logged  # the description itself is never logged


def test_all_secrets_in_one_description_are_removed(settings: Settings) -> None:
    text = " ; ".join(sentence for sentence, _ in SECRETS.values()) + " y no puedo entrar"
    service, repo, _ = _service(settings)
    service.create(_request(text))
    for _, secret in SECRETS.values():
        assert secret not in repo.created[0].descripcion


def test_redacted_text_is_cut_to_the_configured_limit(tmp_path: Path) -> None:
    settings = settings_with_key(tmp_path)
    limit = settings.api.max_description_chars
    # Many short PINs: each placeholder is longer than the secret, so the text grows.
    text = "NIP 1234 " * (limit // 9)
    service, repo, _ = _service(settings)
    service.create(_request(text))
    assert len(repo.created[0].descripcion) <= limit


def test_log_line_has_metadata_only(settings: Settings, caplog: pytest.LogCaptureFixture) -> None:
    service, _, _ = _service(settings)
    with caplog.at_level(logging.INFO, logger="src.api.ticket_service"):
        response = service.create(_request("La VPN es intermitente"))
    record = next(r for r in caplog.records if r.getMessage() == "Ticket created")
    assert record.__dict__["ticket_id"] == response.ticket_id
    assert record.__dict__["prioridad"] == "P3"
    assert record.__dict__["categoria"] == "Conectividad"
    assert "VPN" not in str(record.__dict__)


def test_repository_failure_propagates_as_unavailable(settings: Settings) -> None:
    service, repo, _ = _service(settings)
    repo.error = RepositoryUnavailableError("sqlite")
    with pytest.raises(RepositoryUnavailableError):
        service.create(_request("La VPN es intermitente"))
