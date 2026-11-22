"""Shared fakes and builders for the evaluation runner tests (T21)."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import httpx

from src.api.evaluation import (
    CaseResult,
    EvalCase,
    SearchOutcome,
    TicketOutcome,
    parse_expected,
    run_cases,
)

HEADER = "id,pregunta,intencion,esperado,obtenido,resultado,notas"
PASSWORD = "Altiplano#2026"
CARD = "4111 1111 1111 1111"
SEC_QUESTION = f"No entro al correo, mi contraseña es {PASSWORD} ¿qué hago?"
CARD_QUESTION = f"My card {CARD} was blocked"
API_URL = "http://eval.test"
API_KEY = "k-" + "x" * 30
CASES_FILE = Path(__file__).resolve().parents[1] / "eval" / "cases.csv"

Handler = Callable[[httpx.Request], httpx.Response]


# --- helpers -----------------------------------------------------------------------


def _write_cases(path: Path, rows: list[tuple[str, str, str, str]], header: str = HEADER) -> Path:
    lines = [header]
    for case_id, question, intent, expected in rows:
        lines.append(",".join(f'"{v}"' for v in (case_id, question, intent, expected, "", "", "")))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def _case(case_id: str, esperado: str, pregunta: str = "pregunta") -> EvalCase:
    return EvalCase(case_id, pregunta, "", esperado, parse_expected(esperado))


def _result(case: EvalCase, passed: bool) -> CaseResult:
    return CaseResult(case, passed, "obtenido", "", 1.0)


def _search(
    status: str = "answered",
    top3: list[str] | None = None,
    text: str = "Pasos del articulo.",
    warn: bool = False,
) -> SearchOutcome:
    return SearchOutcome(status, ["KB-001"] if top3 is None else top3, text, warn)


def _ticket(
    categoria: str = "Accesos",
    prioridad: str = "P2",
    escalado: bool = False,
    warn: bool = False,
    response_text: str = "{}",
    persisted: str | None = None,
) -> TicketOutcome:
    return TicketOutcome(categoria, "Sub", prioridad, escalado, warn, response_text, persisted)


class FakeBackend:
    """Scripted backend: ``search_fn`` / ``ticket_fn`` receive the question."""

    def __init__(
        self,
        search_fn: Callable[[str], SearchOutcome] | None = None,
        ticket_fn: Callable[[str], TicketOutcome] | None = None,
        logs: str | None = "",
    ) -> None:
        self.search_fn = search_fn or (lambda q: _search())
        self.ticket_fn = ticket_fn or (lambda q: _ticket())
        self.logs = logs
        self.closed = False
        self.questions: list[str] = []

    def search(self, query: str) -> SearchOutcome:
        self.questions.append(query)
        return self.search_fn(query)

    def create_ticket(self, description: str) -> TicketOutcome:
        self.questions.append(description)
        return self.ticket_fn(description)

    def logs_since_last_call(self) -> str | None:
        return self.logs

    def close(self) -> None:
        self.closed = True


def _clock() -> Callable[[], float]:
    """A clock that advances 1 ms per call (so each case takes exactly 1 ms)."""
    ticks = iter(range(10_000))
    return lambda: next(ticks) / 1000.0


def _run(case: EvalCase, backend: FakeBackend) -> CaseResult:
    return run_cases([case], backend, "fake", _clock()).results[0]
