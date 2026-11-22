"""End-to-end evaluation of the agent tools over a CSV of cases (``main.py eval``, T21, S12).

Cases file (UTF-8, header required, extra columns ignored)::

    id,pregunta,intencion,esperado,obtenido,resultado,notas

``id``, ``pregunta``, ``intencion`` and ``esperado`` are inputs; ``obtenido``, ``resultado``
and ``notas`` are filled by the run (any previous value is overwritten). The results file
has the same columns plus a trailing ``latencia_ms``; ``resultado`` is ``pasó`` or ``falló``.
The question is written redacted (RN-05): a pasted secret never reaches the results.

``esperado`` (one of):

- ``articulo:KB-004``: the top-3 articles contain KB-004 and the status is ``answered``.
- ``rechazo``: status ``no_evidence`` ("no lo sé", RN-04).
- ``escalamiento``: status ``mandatory_escalation`` (RN-03).
- ``ticket:categoria=Accesos;prioridad=P1``: ``crear_ticket`` with ``pregunta`` as the
  description; every ``key=value`` must match. Keys: ``categoria``, ``subcategoria``,
  ``prioridad``, ``escalado`` (``true``/``false``); comparison ignores case.
- ``seguridad``: ``pregunta`` pastes a secret (password, PIN, token, card, CURP). Passes
  when both the answer and the created ticket warn about it and the secret appears in
  neither response, in the persisted ticket, nor (in-process) in the logs.

Backends: by default everything runs in process (``AnswerService`` over the ``CURRENT``
index, ``TicketService`` over a temporary copy of the SQLite database, never the repo's
one) with the configured LLM (``none`` needs no key). With ``api_url`` it calls the real
HTTP API with ``X-API-Key``; then top-3 is the cited article (the API returns only that
one), tickets are created in the server's database and persistence/logs cannot be checked.

Metrics (requirements section 12) and thresholds:

- ``retrieval_top3``: ``articulo`` cases passed, >= 90%.
- ``rechazo``: ``rechazo`` cases passed, 100%.
- ``clasificacion``: ``ticket`` cases passed, >= 85%.
- ``seguridad``: ``seguridad`` cases passed, 100%.
- ``aprobados``: all cases passed, >= 27 of 30 (90%, rounded up).

A metric with no cases is "n/a" and does not fail. Targets and ``known_failures`` come from
the ``eval:`` section of ``config.yaml`` (defaults = section 12).

Exit-code contract (see docs/features/eval-e2e.md):

- 0: every target criterion met and no case failed.
- 3: the global minimum (``min_passed``) and security hold and no NEW case failed, but some
  criterion is unmet or a documented ``known_failures`` case failed (separate report).
- 1: the global minimum or security broke, or a case NOT in ``known_failures`` failed
  (regression). 1 never means "target not met" any more (it did before this contract).
- 2: configuration, cases file, database, index or API error.

Logs carry ids, counts and statuses only, never questions or answers.
"""

from __future__ import annotations

import csv
import json
import logging
import math
import sqlite3
import tempfile
import time
from collections.abc import Callable, Iterator, Sequence
from contextlib import closing, contextmanager
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal, Protocol

import httpx

from src.api.repository import SqlTicketRepository, build_sqlite_repository
from src.api.schemas import build_create_request, build_search_request
from src.api.ticket_service import TicketService
from src.utils.config import ConfigError, EvalConfig, Settings, require_api_key
from src.utils.redaction import redact, sensitive_values

logger = logging.getLogger(__name__)

EXIT_OK = 0
EXIT_REGRESSION = 1
EXIT_ERROR = 2
EXIT_TARGETS_NOT_MET = 3

PASSED = "pasó"
FAILED = "falló"
INPUT_COLUMNS = ("id", "pregunta", "intencion", "esperado", "obtenido", "resultado", "notas")
OUTPUT_COLUMNS = (*INPUT_COLUMNS, "latencia_ms")
REQUIRED_COLUMNS = ("id", "pregunta", "intencion", "esperado")
TICKET_KEYS = ("categoria", "subcategoria", "prioridad", "escalado")
SUMMARY_SUFFIX = ".summary.json"
# Fixed, valid values for the fields ``crear_ticket`` needs besides the description.
TICKET_SUCURSAL = "Centro"
TICKET_AREA = "Soporte"
TICKET_CANAL: Literal["Teams"] = "Teams"
HTTP_TIMEOUT_MARGIN_S = 5.0
# Metrics that must hold for the run to be anything but a regression (exit 1 otherwise).
HARD_METRICS = ("seguridad", "aprobados")


class EvalError(RuntimeError):
    """Configuration or infrastructure problem: the run cannot give meaningful results."""


class CaseError(RuntimeError):
    """One case could not be executed; the message is safe to store (no user text)."""


# --- cases ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Expectation:
    kind: str
    article_id: str | None = None
    fields: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class EvalCase:
    id: str
    pregunta: str
    intencion: str
    esperado: str
    expectation: Expectation


def parse_expected(text: str) -> Expectation:
    """Parse an ``esperado`` value; raise ``ValueError`` when it is not one of the formats."""
    value = text.strip()
    kind, _, arg = value.partition(":")
    kind = kind.strip().lower()
    arg = arg.strip()
    if kind in ("rechazo", "escalamiento", "seguridad") and not arg:
        return Expectation(kind)
    if kind == "articulo" and arg.upper().startswith("KB-") and arg[3:].isdigit():
        return Expectation(kind, article_id=arg.upper())
    if kind == "ticket" and arg:
        fields: dict[str, str] = {}
        for part in arg.split(";"):
            key, sep, expected = part.partition("=")
            key, expected = key.strip().lower(), expected.strip()
            if not sep or key not in TICKET_KEYS or not expected or key in fields:
                raise ValueError(f"invalid ticket expectation {part.strip()!r}")
            if key == "escalado" and expected.lower() not in ("true", "false"):
                raise ValueError("escalado must be true or false")
            fields[key] = expected
        return Expectation(kind, fields=fields)
    raise ValueError(f"unknown esperado {value!r}")


def load_cases(path: Path) -> list[EvalCase]:
    """Read and validate the cases file; any problem is an ``EvalError`` naming the row."""
    try:
        handle = path.open(encoding="utf-8-sig", newline="")
    except OSError as exc:
        raise EvalError(f"cannot read cases file {path}: {type(exc).__name__}") from exc
    with handle:
        reader = csv.DictReader(handle)
        missing = [c for c in REQUIRED_COLUMNS if c not in (reader.fieldnames or [])]
        if missing:
            raise EvalError(f"cases file lacks the columns: {', '.join(missing)}")
        cases: list[EvalCase] = []
        seen: set[str] = set()
        for line, row in enumerate(reader, start=2):
            case_id = (row.get("id") or "").strip()
            question = (row.get("pregunta") or "").strip()
            if not case_id or not question:
                raise EvalError(f"row {line}: id and pregunta are required")
            if case_id in seen:
                raise EvalError(f"row {line}: duplicate id {case_id}")
            seen.add(case_id)
            try:
                expectation = parse_expected(row.get("esperado") or "")
            except ValueError as exc:
                raise EvalError(f"row {line} ({case_id}): {exc}") from exc
            cases.append(
                EvalCase(
                    case_id,
                    question,
                    (row.get("intencion") or "").strip(),
                    (row.get("esperado") or "").strip(),
                    expectation,
                )
            )
    if not cases:
        raise EvalError(f"no cases in {path}")
    return cases


# --- backends ------------------------------------------------------------------------


@dataclass(frozen=True)
class SearchOutcome:
    status: str
    top3: list[str]
    text: str
    sensitive_warning: bool


@dataclass(frozen=True)
class TicketOutcome:
    categoria: str
    subcategoria: str
    prioridad: str
    escalado: bool
    sensitive_warning: bool
    response_text: str
    persisted_text: str | None


class EvalBackend(Protocol):
    def search(self, query: str) -> SearchOutcome: ...
    def create_ticket(self, description: str) -> TicketOutcome: ...
    def logs_since_last_call(self) -> str | None:
        """Log text produced by the last calls (None when the backend cannot see logs)."""
        ...

    def close(self) -> None: ...


class _LogCapture(logging.Handler):
    """Keeps every log record of a case so a leaked secret can be detected, not stored."""

    def __init__(self) -> None:
        super().__init__(level=logging.DEBUG)
        self.chunks: list[str] = []

    def emit(self, record: logging.LogRecord) -> None:
        extra = {k: v for k, v in record.__dict__.items() if k not in _STD_RECORD_FIELDS}
        self.chunks.append(f"{record.getMessage()} {extra!r}")

    def drain(self) -> str:
        text = "\n".join(self.chunks)
        self.chunks.clear()
        return text


_STD_RECORD_FIELDS = set(logging.makeLogRecord({}).__dict__) | {"message", "asctime"}


class LocalBackend:
    """In-process services: ``CURRENT`` index and a temporary copy of the SQLite database."""

    def __init__(self, settings: Settings) -> None:
        from src.embeddings.factory import build_embedder
        from src.llm.factory import build_llm
        from src.retrieval.answer_service import AnswerService
        from src.retrieval.retriever import RetrievalResult, Retriever
        from src.vectordb.chroma_store import IndexNotFoundError
        from src.vectordb.versions import CurrentStore

        source = settings.paths.sqlite_db
        if not source.is_file():
            raise EvalError(f"database not found ({source.name}); run: python main.py load-db")
        self._tmp = tempfile.TemporaryDirectory(prefix="deskpilot-eval-")
        self._db = Path(self._tmp.name) / "eval.db"
        try:
            self._copy_database(source)
            self._store = CurrentStore.from_settings(settings)
            self._store.get()
        except IndexNotFoundError as exc:
            self._tmp.cleanup()
            raise EvalError("no vector index; run: python main.py index") from exc
        except (sqlite3.Error, OSError) as exc:
            self._tmp.cleanup()
            raise EvalError(f"cannot copy the database: {type(exc).__name__}") from exc

        last: list[RetrievalResult] = []

        class _Recording(Retriever):
            def search(self, query: str, categoria: str | None = None) -> RetrievalResult:
                result = super().search(query, categoria)
                last.append(result)
                return result

        self._last = last
        retriever = _Recording.from_settings(settings, build_embedder(settings), self._store.get)
        llm = build_llm(settings)
        self._answers = AnswerService(retriever, llm, settings)
        self._repository: SqlTicketRepository = build_sqlite_repository(self._db)
        self._tickets = TicketService(self._repository, llm, settings)
        self._search_model = build_search_request(settings.api.max_query_chars)
        self._create_model = build_create_request(settings.api.max_description_chars)
        self._logs = _LogCapture()
        logging.getLogger().addHandler(self._logs)

    def _copy_database(self, source: Path) -> None:
        with (
            closing(sqlite3.connect(f"{source.resolve().as_uri()}?mode=ro", uri=True)) as src,
            closing(sqlite3.connect(self._db)) as dst,
        ):
            src.backup(dst)
            has_table = dst.execute(
                "SELECT 1 FROM sqlite_master WHERE name = 'tickets_nuevos'"
            ).fetchone()
        if has_table is None:
            raise EvalError("database has no tickets_nuevos table; run: python main.py load-db")

    def search(self, query: str) -> SearchOutcome:
        try:
            request = self._search_model(query=query)
        except ValueError as exc:
            raise CaseError("question rejected by the API validation") from exc
        self._last.clear()
        answer = self._answers.answer(request.query)
        articles = self._last[-1].articles if self._last else []
        return SearchOutcome(
            answer.status,
            [a.article_id for a in articles],
            answer.text,
            answer.sensitive_data_warning,
        )

    def create_ticket(self, description: str) -> TicketOutcome:
        try:
            request = self._create_model(
                descripcion=description,
                sucursal=TICKET_SUCURSAL,
                area=TICKET_AREA,
                canal=TICKET_CANAL,
            )
        except ValueError as exc:
            raise CaseError("question rejected by the API validation") from exc
        response = self._tickets.create(request)
        with closing(sqlite3.connect(self._db)) as conn:
            row = conn.execute(
                "SELECT descripcion FROM tickets_nuevos WHERE ticket_id = ?",
                (response.ticket_id,),
            ).fetchone()
        return TicketOutcome(
            response.categoria,
            response.subcategoria,
            response.prioridad,
            response.escalado,
            response.sensitive_data_warning,
            response.model_dump_json(),
            None if row is None else str(row[0]),
        )

    def logs_since_last_call(self) -> str | None:
        return self._logs.drain()

    def close(self) -> None:
        logging.getLogger().removeHandler(self._logs)
        self._store.close()
        self._tmp.cleanup()


class HttpBackend:
    """The real HTTP API with ``X-API-Key``; the key is never printed or logged."""

    def __init__(self, base_url: str, api_key: str, timeout_s: float) -> None:
        self._client = httpx.Client(
            base_url=base_url.rstrip("/"),
            headers={"X-API-Key": api_key},
            timeout=timeout_s,
            follow_redirects=False,
        )

    def _post(self, path: str, body: dict[str, str]) -> dict[str, Any]:
        try:
            response = self._client.post(path, json=body)
        except httpx.TransportError as exc:
            raise EvalError(f"API unreachable: {type(exc).__name__}") from exc
        if response.status_code in (401, 403):
            raise EvalError("the API rejected the key (401); check --api-key / DESKPILOT_API_KEY")
        if response.status_code not in (200, 201):
            raise CaseError(f"http {response.status_code}")
        try:
            data = response.json()
        except ValueError as exc:
            raise CaseError("response is not JSON") from exc
        if not isinstance(data, dict):
            raise CaseError("unexpected response shape")
        return data

    def search(self, query: str) -> SearchOutcome:
        data = self._post("/buscar_solucion", {"query": query})
        try:
            return SearchOutcome(
                str(data["status"]),
                [str(c["article_id"]) for c in data["citations"]],
                str(data["text"]),
                bool(data["sensitive_data_warning"]),
            )
        except (KeyError, TypeError) as exc:
            raise CaseError("unexpected response shape") from exc

    def create_ticket(self, description: str) -> TicketOutcome:
        data = self._post(
            "/tickets",
            {
                "descripcion": description,
                "sucursal": TICKET_SUCURSAL,
                "area": TICKET_AREA,
                "canal": TICKET_CANAL,
            },
        )
        try:
            return TicketOutcome(
                str(data["categoria"]),
                str(data["subcategoria"]),
                str(data["prioridad"]),
                bool(data["escalado"]),
                bool(data["sensitive_data_warning"]),
                json.dumps(data, ensure_ascii=False),
                None,
            )
        except KeyError as exc:
            raise CaseError("unexpected response shape") from exc

    def logs_since_last_call(self) -> str | None:
        return None

    def close(self) -> None:
        self._client.close()


@contextmanager
def open_backend(
    settings: Settings, api_url: str | None = None, api_key: str | None = None
) -> Iterator[EvalBackend]:
    """Local backend by default; HTTP backend when ``api_url`` is given (key required)."""
    backend: EvalBackend
    if api_url:
        if not api_url.startswith(("http://", "https://")):
            raise EvalError("--api-url must start with http:// or https://")
        key = api_key
        if key is None:
            try:
                key = require_api_key(settings, "eval").get_secret_value()
            except ConfigError as exc:
                raise EvalError(str(exc)) from exc
        if not key:
            raise EvalError("the API key is empty")
        backend = HttpBackend(api_url, key, settings.api.request_timeout_s + HTTP_TIMEOUT_MARGIN_S)
    else:
        backend = LocalBackend(settings)
    try:
        yield backend
    finally:
        backend.close()


# --- running cases -------------------------------------------------------------------


@dataclass(frozen=True)
class CaseResult:
    case: EvalCase
    passed: bool
    obtenido: str
    notas: str
    latencia_ms: float


def _check_ticket(expected: dict[str, str], got: TicketOutcome) -> tuple[bool, str]:
    actual = {
        "categoria": got.categoria,
        "subcategoria": got.subcategoria,
        "prioridad": got.prioridad,
        "escalado": str(got.escalado).lower(),
    }
    wrong = [
        f"{key}: esperado {value}, obtenido {actual[key]}"
        for key, value in expected.items()
        if actual[key].casefold() != value.casefold()
    ]
    return not wrong, "; ".join(wrong)


def _leaks(secrets: Sequence[str], haystacks: dict[str, str | None]) -> list[str]:
    """Names of the places where a secret (or its digits-only form) appears."""
    found: list[str] = []
    for place, text in haystacks.items():
        if not text:
            continue
        squashed = "".join(ch for ch in text if ch.isalnum())
        for secret in secrets:
            digits = "".join(ch for ch in secret if ch.isalnum())
            if secret in text or (len(digits) >= 8 and digits in squashed):
                found.append(place)
                break
    return found


def _evaluate(case: EvalCase, backend: EvalBackend) -> tuple[bool, str, str]:
    expectation = case.expectation
    kind = expectation.kind
    if kind == "ticket":
        ticket = backend.create_ticket(case.pregunta)
        ok, notes = _check_ticket(expectation.fields, ticket)
        obtenido = (
            f"categoria={ticket.categoria}; prioridad={ticket.prioridad}; "
            f"escalado={str(ticket.escalado).lower()}"
        )
        return ok, obtenido, notes
    if kind == "seguridad":
        secrets = sensitive_values(case.pregunta)
        if not secrets:
            return False, "sin secreto detectado", "pregunta has no detectable secret"
        answer = backend.search(case.pregunta)
        ticket = backend.create_ticket(case.pregunta)
        leaks = _leaks(
            secrets,
            {
                "respuesta": answer.text,
                "ticket": ticket.response_text,
                "persistido": ticket.persisted_text,
                "logs": backend.logs_since_last_call(),
            },
        )
        warned = answer.sensitive_warning and ticket.sensitive_warning
        problems = [f"secreto filtrado en: {', '.join(leaks)}"] if leaks else []
        if not warned:
            problems.append("no advierte sobre datos sensibles")
        obtenido = f"advertencia={'si' if warned else 'no'}; fugas={len(leaks)}"
        return not leaks and warned, obtenido, "; ".join(problems)
    answer = backend.search(case.pregunta)
    top = ",".join(answer.top3) or "-"
    obtenido = f"status={answer.status}; top3={top}"
    if kind == "articulo":
        found = expectation.article_id in answer.top3
        ok = found and answer.status == "answered"
        misses: list[str] = []
        if not found:
            misses.append(f"{expectation.article_id} no esta en el top-3")
        if answer.status != "answered":
            misses.append(f"status {answer.status}")
        return ok, obtenido, "; ".join(misses)
    wanted = "no_evidence" if kind == "rechazo" else "mandatory_escalation"
    ok = answer.status == wanted
    return ok, obtenido, "" if ok else f"esperado status {wanted}"


def run_case(case: EvalCase, backend: EvalBackend, clock: Callable[[], float]) -> CaseResult:
    """Run one case; a ``CaseError`` fails the case, an ``EvalError`` aborts the run."""
    started = clock()
    try:
        passed, obtenido, notes = _evaluate(case, backend)
    except CaseError as exc:
        passed, obtenido, notes = False, "error", str(exc)
    except EvalError:
        raise
    except Exception as exc:
        # Type only: the message of an unexpected error may quote user text.
        passed, obtenido, notes = False, "error", f"unexpected {type(exc).__name__}"
    elapsed_ms = (clock() - started) * 1000.0
    logger.info(
        "Eval case finished",
        extra={"case_id": case.id, "kind": case.expectation.kind, "passed": passed},
    )
    return CaseResult(case, passed, obtenido, notes, round(elapsed_ms, 1))


# --- metrics -------------------------------------------------------------------------


@dataclass(frozen=True)
class Metric:
    name: str
    passed: int
    total: int
    threshold: float
    required: int

    @property
    def pct(self) -> float | None:
        return None if self.total == 0 else round(100.0 * self.passed / self.total, 1)

    @property
    def met(self) -> bool:
        return self.total == 0 or self.passed >= self.required


def _required(total: int, fraction: float) -> int:
    """Smallest count reaching ``fraction`` of ``total`` (integer math, no float error)."""
    percent = round(fraction * 100)
    return -(-total * percent // 100)


def thresholds_by_metric(config: EvalConfig) -> dict[str, float]:
    """Metric name -> minimum fraction, from the ``eval.thresholds`` percentages."""
    t = config.thresholds
    return {
        "retrieval_top3": t.retrieval_top3_pct / 100,
        "rechazo": t.rejection_pct / 100,
        "clasificacion": t.classification_pct / 100,
        "seguridad": t.security_pct / 100,
        "aprobados": t.min_passed / 100,
    }


def compute_metrics(
    results: Sequence[CaseResult], config: EvalConfig | None = None
) -> list[Metric]:
    thresholds = thresholds_by_metric(config or EvalConfig())
    by_kind = {
        "retrieval_top3": "articulo",
        "rechazo": "rechazo",
        "clasificacion": "ticket",
        "seguridad": "seguridad",
    }
    metrics: list[Metric] = []
    for name, kind in by_kind.items():
        subset = [r for r in results if r.case.expectation.kind == kind]
        total = len(subset)
        metrics.append(
            Metric(
                name,
                sum(r.passed for r in subset),
                total,
                thresholds[name],
                _required(total, thresholds[name]),
            )
        )
    total = len(results)
    metrics.append(
        Metric(
            "aprobados",
            sum(r.passed for r in results),
            total,
            thresholds["aprobados"],
            _required(total, thresholds["aprobados"]),
        )
    )
    return metrics


def percentile(values: Sequence[float], q: float) -> float:
    """Nearest-rank percentile (``q`` in 0..100) of a non-empty sequence."""
    ordered = sorted(values)
    rank = max(1, math.ceil(q / 100.0 * len(ordered)))
    return ordered[rank - 1]


@dataclass(frozen=True)
class EvalReport:
    results: list[CaseResult]
    metrics: list[Metric]
    p50_ms: float
    p95_ms: float
    backend: str
    config: EvalConfig = field(default_factory=EvalConfig)

    @property
    def thresholds_met(self) -> bool:
        return all(m.met for m in self.metrics)

    @property
    def failed_ids(self) -> list[str]:
        return [r.case.id for r in self.results if not r.passed]

    @property
    def known_failures_hit(self) -> list[str]:
        known = {k.id for k in self.config.known_failures}
        return [i for i in self.failed_ids if i in known]

    @property
    def known_failures_fixed(self) -> list[str]:
        """Known failures that passed in this run (stale entries to remove from the config)."""
        failed = set(self.failed_ids)
        return [k.id for k in self.config.known_failures if k.id not in failed]

    @property
    def new_failures(self) -> list[str]:
        known = {k.id for k in self.config.known_failures}
        return [i for i in self.failed_ids if i not in known]

    @property
    def unmet(self) -> list[Metric]:
        return [m for m in self.metrics if not m.met]

    @property
    def exit_code(self) -> int:
        return self.verdict[0]

    @property
    def verdict(self) -> tuple[int, str]:
        """(exit code, reason) per the contract in the module docstring."""
        broken = [m.name for m in self.unmet if m.name in HARD_METRICS]
        if broken:
            return EXIT_REGRESSION, f"global minimum or security broken: {', '.join(broken)}"
        if self.new_failures:
            ids = ", ".join(self.new_failures)
            return EXIT_REGRESSION, f"new failures not in known_failures: {ids}"
        if self.unmet or self.known_failures_hit:
            unmet = ", ".join(m.name for m in self.unmet) or "none"
            hit = ", ".join(self.known_failures_hit) or "none"
            return EXIT_TARGETS_NOT_MET, f"criteria not met: {unmet}; known failures: {hit}"
        return EXIT_OK, "all target criteria met"


def run_cases(
    cases: Sequence[EvalCase],
    backend: EvalBackend,
    backend_name: str,
    clock: Callable[[], float] = time.perf_counter,
    config: EvalConfig | None = None,
) -> EvalReport:
    config = config or EvalConfig()
    results = [run_case(case, backend, clock) for case in cases]
    latencies = [r.latencia_ms for r in results]
    return EvalReport(
        results,
        compute_metrics(results, config),
        percentile(latencies, 50),
        percentile(latencies, 95),
        backend_name,
        config,
    )


# --- output --------------------------------------------------------------------------


def summary_path(out: Path) -> Path:
    return out.with_name(out.stem + SUMMARY_SUFFIX)


def write_results(report: EvalReport, out: Path) -> Path:
    """Write ``out`` (CSV) and the JSON summary next to it; return the summary path."""
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(OUTPUT_COLUMNS)
        for r in report.results:
            writer.writerow(
                [
                    r.case.id,
                    redact(r.case.pregunta),
                    r.case.intencion,
                    r.case.esperado,
                    r.obtenido,
                    PASSED if r.passed else FAILED,
                    r.notas,
                    f"{r.latencia_ms:.1f}",
                ]
            )
    total = len(report.results)
    summary = {
        "generated_at": datetime.now(UTC).replace(microsecond=0).isoformat(),
        "backend": report.backend,
        "total": total,
        "passed": sum(r.passed for r in report.results),
        "thresholds_met": report.thresholds_met,
        "exit_code": report.exit_code,
        "exit_reason": report.verdict[1],
        "criteria": {
            m.name: {"target": round(m.threshold * 100), "actual": m.pct, "met": m.met}
            for m in report.metrics
        },
        "known_failures_hit": report.known_failures_hit,
        "known_failures_fixed": report.known_failures_fixed,
        "new_failures": report.new_failures,
        "metrics": {
            m.name: {
                "passed": m.passed,
                "total": m.total,
                "pct": m.pct,
                "threshold_pct": round(m.threshold * 100),
                "required": m.required,
                "met": m.met,
            }
            for m in report.metrics
        },
        "latency_ms": {"p50": report.p50_ms, "p95": report.p95_ms},
        "cases": {r.case.id: PASSED if r.passed else FAILED for r in report.results},
    }
    path = summary_path(out)
    path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def format_report(report: EvalReport) -> str:
    """Console summary: one line per metric, latency and the verdict (no user text)."""
    lines = []
    for m in report.metrics:
        pct = "n/a" if m.pct is None else f"{m.pct:.1f}%"
        state = "ok" if m.met else "BELOW"
        lines.append(
            f"  {m.name:<15} {m.passed}/{m.total}  {pct:>6}  "
            f"(goal >= {round(m.threshold * 100)}%)  {state}"
        )
    lines.append(f"  latency per case: p50 {report.p50_ms:.1f} ms, p95 {report.p95_ms:.1f} ms")
    reasons = {k.id: k.reason for k in report.config.known_failures}
    failed = report.failed_ids
    lines.append(f"  failed cases: {', '.join(failed) if failed else 'none'}")
    for case_id in report.known_failures_hit:
        lines.append(f"  known failure {case_id}: {reasons[case_id]}")
    for case_id in report.new_failures:
        lines.append(f"  NEW failure {case_id}: not in eval.known_failures (regression)")
    for case_id in report.known_failures_fixed:
        lines.append(f"  known failure {case_id} now passes: remove it from eval.known_failures")
    if report.unmet:
        lines.append("  criteria not met: " + ", ".join(m.name for m in report.unmet))
    code, reason = report.verdict
    lines.append(f"  verdict: exit {code} ({reason})")
    return "\n".join(lines)


def run_eval(
    settings: Settings,
    cases_path: Path,
    out_path: Path,
    api_url: str | None = None,
    api_key: str | None = None,
) -> tuple[EvalReport, Path]:
    """Load cases, run them on the chosen backend and write the results and summary."""
    if cases_path.resolve() == out_path.resolve():
        raise EvalError("--out must not be the cases file")
    cases = load_cases(cases_path)
    unknown = sorted({k.id for k in settings.eval.known_failures} - {c.id for c in cases})
    if unknown:
        raise EvalError(f"eval.known_failures ids not in the cases file: {', '.join(unknown)}")
    with open_backend(settings, api_url, api_key) as backend:
        report = run_cases(cases, backend, "http" if api_url else "local", config=settings.eval)
    return report, write_results(report, out_path)
