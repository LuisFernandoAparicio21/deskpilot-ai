"""Deterministic synthetic ticket generator for Banco Altiplano (S3, RF-22, RNF-11).

``generate_dataset`` writes three UTF-8 CSV files (``\\n`` line endings, so the same seed
gives the same bytes and the same hash on every OS):

- ``<raw>/tickets.csv``: ``n`` tickets with the 17 fields of section 11, in that order.
- ``<raw>/sucursales.csv``: branch dimension for JOINs (city, state, region, es_foranea).
- ``<sample>/tickets_sample.csv``: a *systematic* sample of 200 tickets (every
  ``n // 200``-th row of the full file, starting with the first). Unlike the first 200
  rows, which cover only the first days of the period, it spans the 12 months and keeps
  the patterns.

All randomness comes from a local ``random.Random(seed)``; the global state is never
touched. Dates belong to the fixed period 2025-11-01 .. 2026-10-31 and the snapshot time
is ``REFERENCE_TIME`` (end of the period), never "now".

Business rules applied:

- Subcategory weights put ~40% of tickets in the 5 repetitive subcategories
  (``es_repetitivo = 1`` exactly for those, problem 1 of section 2).
- "Desbloqueo de usuario" is twice as likely on payday days 14–16 and 29–31, and every
  ticket opened on those days takes 20% longer (problem 2).
- Branches outside CDMX, Guadalajara and Monterrey resolve slower (problem 3).
- Priority by subcategory impact (RN-01) and ``sla_horas`` from config (RN-02);
  ``sla_cumplido = horas_resolucion <= sla_horas``.
- ~10% of tickets are in English, with the solution text in English.
- Tickets whose resolution would end after ``REFERENCE_TIME`` stay ``abierto`` or
  ``en_proceso`` with empty ``fecha_cierre``, ``horas_resolucion`` and ``sla_cumplido``;
  tickets closed in the last 72 h are ``resuelto`` and older ones ``cerrado``.
"""

from __future__ import annotations

import csv
import logging
import math
import random
from collections import Counter
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from itertools import accumulate
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict

from src.ingestion.ticket_catalog import (
    AREAS,
    CHANNELS,
    CITIES,
    ESCALATION_PREFIX,
    METRO_CITIES,
    SUBCATEGORIES,
    SubcategorySpec,
)

logger = logging.getLogger(__name__)

Priority = Literal["P1", "P2", "P3", "P4"]
Language = Literal["es", "en"]
State = Literal["abierto", "en_proceso", "resuelto", "cerrado"]

TICKET_FIELDS: tuple[str, ...] = (
    "ticket_id", "fecha_apertura", "fecha_cierre", "categoria", "subcategoria", "prioridad",
    "sucursal", "area", "canal", "sla_horas", "sla_cumplido", "horas_resolucion", "anio_mes",
    "solucion", "es_repetitivo", "idioma", "estado",
)  # fmt: skip
SUCURSAL_FIELDS: tuple[str, ...] = ("sucursal", "ciudad", "estado_mx", "region", "es_foranea")

PERIOD_START = date(2025, 11, 1)
PERIOD_END = date(2026, 10, 31)  # inclusive
REFERENCE_TIME = datetime(2026, 11, 1)  # snapshot: end of the period
QUINCENA_DAYS: frozenset[int] = frozenset({14, 15, 16, 29, 30, 31})
UNLOCK_SUBCATEGORY = "Desbloqueo de usuario"
SAMPLE_SIZE = 200

PRIORITIES: tuple[Priority, ...] = ("P1", "P2", "P3", "P4")
CANALES: tuple[str, ...] = tuple(name for name, _ in CHANNELS)
ESTADOS: tuple[str, ...] = ("abierto", "en_proceso", "resuelto", "cerrado")

DATE_FORMAT = "%Y-%m-%d %H:%M:%S"
ENGLISH_RATE = 0.10
UNLOCK_PAYDAY_FACTOR = 2.0
PAYDAY_DELAY_FACTOR = 1.2
ESCALATION_DELAY_FACTOR = 1.6
# Resolution time = SLA * lognormal factor; the median factor is higher for foráneas.
MEDIAN_SLA_FACTOR = {False: 0.45, True: 0.65}  # keyed by es_foranea
RESOLUTION_SIGMA = 0.6
METRO_BRANCH_WEIGHT = 1.3  # metro branches are busier than foráneas
MIN_RESOLUTION_MINUTES = 5
RESOLVED_WINDOW = timedelta(hours=72)
WEEKDAY_WEIGHTS = (1.0, 1.0, 1.0, 1.0, 1.0, 0.4, 0.1)  # Monday .. Sunday
HOUR_WEIGHTS = (0, 0, 0, 0, 0, 0, 0, 1, 6, 10, 10, 9, 8, 7, 8, 9, 8, 6, 4, 2, 1, 0, 0, 0)


class Sucursal(BaseModel):
    """One row of the branch dimension."""

    model_config = ConfigDict(frozen=True)

    sucursal: str
    ciudad: str
    estado_mx: str
    region: str
    es_foranea: bool

    def to_row(self) -> list[str]:
        return [self.sucursal, self.ciudad, self.estado_mx, self.region, _flag(self.es_foranea)]


class Ticket(BaseModel):
    """One synthetic ticket with the 17 fields of requirements section 11."""

    model_config = ConfigDict(frozen=True)

    ticket_id: str
    fecha_apertura: datetime
    fecha_cierre: datetime | None
    categoria: str
    subcategoria: str
    prioridad: Priority
    sucursal: str
    area: str
    canal: str
    sla_horas: int
    sla_cumplido: bool | None
    horas_resolucion: float | None
    anio_mes: str
    solucion: str
    es_repetitivo: bool
    idioma: Language
    estado: State

    def to_row(self) -> list[str]:
        return [
            self.ticket_id,
            self.fecha_apertura.strftime(DATE_FORMAT),
            self.fecha_cierre.strftime(DATE_FORMAT) if self.fecha_cierre else "",
            self.categoria,
            self.subcategoria,
            self.prioridad,
            self.sucursal,
            self.area,
            self.canal,
            str(self.sla_horas),
            "" if self.sla_cumplido is None else _flag(self.sla_cumplido),
            "" if self.horas_resolucion is None else f"{self.horas_resolucion:.2f}",
            self.anio_mes,
            self.solucion,
            _flag(self.es_repetitivo),
            self.idioma,
            self.estado,
        ]


@dataclass(frozen=True)
class PatternStats:
    """Measured business patterns, to report and to check the thresholds of S3."""

    repetitive_share: float
    payday_unlock_ratio: float
    sla_metro_pct: float
    sla_foranea_pct: float
    sla_gap_pp: float
    english_share: float
    open_tickets: int


@dataclass(frozen=True)
class DatasetResult:
    """Paths and figures of one ``generate_dataset`` run."""

    tickets_path: Path
    sucursales_path: Path
    sample_path: Path
    n_tickets: int
    n_sucursales: int
    sample_size: int
    stats: PatternStats


def _flag(value: bool) -> str:
    return "1" if value else "0"


def build_sucursales() -> list[Sucursal]:
    """Return the fixed branch dimension (no randomness involved)."""
    return [
        Sucursal(
            sucursal=f"{city} {number:02d}",
            ciudad=city,
            estado_mx=state,
            region=region,
            es_foranea=city not in METRO_CITIES,
        )
        for city, state, region, count in CITIES
        for number in range(1, count + 1)
    ]


def _validate(n: int, sla_horas: Mapping[str, int]) -> dict[str, int]:
    if n < 1:
        raise ValueError(f"n must be a positive number of tickets, got {n}")
    missing = [p for p in PRIORITIES if p not in sla_horas]
    invalid = [p for p in PRIORITIES if p in sla_horas and int(sla_horas[p]) <= 0]
    if missing or invalid:
        raise ValueError(
            f"sla_horas needs a positive number of hours for {', '.join(PRIORITIES)} "
            f"(missing: {missing or 'none'}, not positive: {invalid or 'none'})"
        )
    return {p: int(sla_horas[p]) for p in PRIORITIES}


def _period_days() -> list[date]:
    return [PERIOD_START + timedelta(d) for d in range((PERIOD_END - PERIOD_START).days + 1)]


def _cum(weights: Iterable[float]) -> list[float]:
    return list(accumulate(weights))


def _state(opened: datetime, closed: datetime, sla_hours: int) -> State:
    if closed > REFERENCE_TIME:
        waiting = REFERENCE_TIME - opened < timedelta(hours=sla_hours / 2)
        return "abierto" if waiting else "en_proceso"
    return "resuelto" if REFERENCE_TIME - closed <= RESOLVED_WINDOW else "cerrado"


def generate_tickets(seed: int, n: int, sla_horas: Mapping[str, int]) -> list[Ticket]:
    """Generate ``n`` tickets sorted by opening time; same ``seed`` => same tickets."""
    sla = _validate(n, sla_horas)
    rng = random.Random(seed)
    days = _period_days()
    base_day = [WEEKDAY_WEIGHTS[d.weekday()] for d in days]
    unlock_day = [
        w * (UNLOCK_PAYDAY_FACTOR if d.day in QUINCENA_DAYS else 1.0)
        for d, w in zip(days, base_day, strict=True)
    ]
    day_cum = {False: _cum(base_day), True: _cum(unlock_day)}
    branches = build_sucursales()
    branch_cum = _cum(1.0 if b.es_foranea else METRO_BRANCH_WEIGHT for b in branches)
    sub_cum = _cum(s.weight for s in SUBCATEGORIES)
    area_names = [name for name, _ in AREAS]
    area_cum = _cum(w for _, w in AREAS)
    channel_cum = _cum(w for _, w in CHANNELS)
    hour_cum = _cum(HOUR_WEIGHTS)

    drafts: list[tuple[datetime, int, dict[str, object]]] = []
    for index in range(n):
        spec: SubcategorySpec = rng.choices(SUBCATEGORIES, cum_weights=sub_cum)[0]
        day = rng.choices(days, cum_weights=day_cum[spec.name == UNLOCK_SUBCATEGORY])[0]
        hour = rng.choices(range(24), cum_weights=hour_cum)[0]
        opened = datetime(day.year, day.month, day.day, hour, rng.randrange(60), rng.randrange(60))
        priority: Priority = rng.choices(PRIORITIES, weights=spec.priority_weights)[0]
        branch = rng.choices(branches, cum_weights=branch_cum)[0]
        area = (
            rng.choice(spec.areas)
            if spec.areas
            else rng.choices(area_names, cum_weights=area_cum)[0]
        )
        channel = rng.choices(CANALES, cum_weights=channel_cum)[0]
        language: Language = "en" if rng.random() < ENGLISH_RATE else "es"
        escalated = rng.random() < spec.escalation_rate
        texts = spec.solutions_en if language == "en" else spec.solutions_es
        solution = rng.choice(texts)
        if escalated:
            solution = ESCALATION_PREFIX[language] + solution

        factor = MEDIAN_SLA_FACTOR[branch.es_foranea] * math.exp(rng.gauss(0, RESOLUTION_SIGMA))
        if day.day in QUINCENA_DAYS:
            factor *= PAYDAY_DELAY_FACTOR
        if escalated:
            factor *= ESCALATION_DELAY_FACTOR
        minutes = max(MIN_RESOLUTION_MINUTES, round(sla[priority] * 60 * factor))
        closed = opened + timedelta(minutes=minutes)
        state = _state(opened, closed, sla[priority])
        is_open = state in ("abierto", "en_proceso")
        hours = round(minutes / 60, 2)

        drafts.append(
            (
                opened,
                index,
                {
                    "fecha_apertura": opened,
                    "fecha_cierre": None if is_open else closed,
                    "categoria": spec.categoria,
                    "subcategoria": spec.name,
                    "prioridad": priority,
                    "sucursal": branch.sucursal,
                    "area": area,
                    "canal": channel,
                    "sla_horas": sla[priority],
                    "sla_cumplido": None if is_open else hours <= sla[priority],
                    "horas_resolucion": None if is_open else hours,
                    "anio_mes": opened.strftime("%Y-%m"),
                    "solucion": solution,
                    "es_repetitivo": spec.repetitive,
                    "idioma": language,
                    "estado": state,
                },
            )
        )

    drafts.sort(key=lambda draft: (draft[0], draft[1]))
    return [
        Ticket.model_validate({"ticket_id": f"TCK-{number:06d}", **fields})
        for number, (_opened, _index, fields) in enumerate(drafts, start=1)
    ]


def sample_tickets(tickets: Sequence[Ticket], size: int = SAMPLE_SIZE) -> list[Ticket]:
    """Systematic sample: every ``len // size``-th ticket, starting with the first."""
    step = max(1, len(tickets) // size)
    return list(tickets[::step][:size])


def pattern_stats(tickets: Sequence[Ticket], sucursales: Sequence[Sucursal]) -> PatternStats:
    """Measure the patterns of section 11 on ``tickets``."""
    total = len(tickets)
    foranea = {s.sucursal: s.es_foranea for s in sucursales}
    days = _period_days()
    peak_days = sum(d.day in QUINCENA_DAYS for d in days)
    unlocks = Counter(
        t.fecha_apertura.day in QUINCENA_DAYS
        for t in tickets
        if t.subcategoria == UNLOCK_SUBCATEGORY
    )
    rest_rate = unlocks[False] / (len(days) - peak_days)
    peak_rate = unlocks[True] / peak_days

    def compliance(is_foranea: bool) -> float:
        closed = [
            t.sla_cumplido
            for t in tickets
            if t.sla_cumplido is not None and foranea[t.sucursal] is is_foranea
        ]
        return 100 * sum(closed) / len(closed) if closed else 0.0

    metro, outside = compliance(False), compliance(True)
    return PatternStats(
        repetitive_share=sum(t.es_repetitivo for t in tickets) / total,
        payday_unlock_ratio=peak_rate / rest_rate if rest_rate else math.inf,
        sla_metro_pct=metro,
        sla_foranea_pct=outside,
        sla_gap_pp=metro - outside,
        english_share=sum(t.idioma == "en" for t in tickets) / total,
        open_tickets=sum(t.fecha_cierre is None for t in tickets),
    )


def _write_csv(path: Path, header: Sequence[str], rows: Iterable[list[str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(header)
        writer.writerows(rows)


def generate_dataset(
    seed: int,
    n: int,
    raw_dir: Path,
    sample_dir: Path,
    sla_horas: Mapping[str, int],
) -> DatasetResult:
    """Generate the tickets and write ``tickets.csv``, ``sucursales.csv`` and the sample."""
    tickets = generate_tickets(seed, n, sla_horas)
    sucursales = build_sucursales()
    sample = sample_tickets(tickets)
    result = DatasetResult(
        tickets_path=raw_dir / "tickets.csv",
        sucursales_path=raw_dir / "sucursales.csv",
        sample_path=sample_dir / "tickets_sample.csv",
        n_tickets=len(tickets),
        n_sucursales=len(sucursales),
        sample_size=len(sample),
        stats=pattern_stats(tickets, sucursales),
    )
    _write_csv(result.tickets_path, TICKET_FIELDS, (t.to_row() for t in tickets))
    _write_csv(result.sucursales_path, SUCURSAL_FIELDS, (s.to_row() for s in sucursales))
    _write_csv(result.sample_path, TICKET_FIELDS, (t.to_row() for t in sample))
    logger.info(
        "synthetic dataset written",
        extra={"seed": seed, "n_tickets": result.n_tickets, "stats": vars(result.stats)},
    )
    return result
