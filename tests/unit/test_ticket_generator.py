"""Unit tests for the synthetic ticket generator (S3, RF-22, RNF-11).

The metrics are recomputed here from the written CSV files, independently of
``pattern_stats``, so a bug in the generator's own statistics cannot hide a broken
pattern.
"""

from __future__ import annotations

import csv
import hashlib
from collections import Counter
from datetime import date, datetime, timedelta
from pathlib import Path

import pytest

from src.ingestion import ticket_generator as tg
from src.ingestion.ticket_catalog import (
    KB_SUBCATEGORIES,
    METRO_CITIES,
    REPETITIVE_SUBCATEGORIES,
    SUBCATEGORIES,
)

SEED = 42
N = 5000
SLA = {"P1": 4, "P2": 8, "P3": 24, "P4": 72}
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

Row = dict[str, str]


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _read(path: Path) -> tuple[list[str], list[Row]]:
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        rows = list(reader)
        return list(reader.fieldnames or []), rows


def _dt(value: str) -> datetime:
    return datetime.strptime(value, DATE_FORMAT)


def _closed(rows: list[Row]) -> list[Row]:
    return [r for r in rows if r["fecha_cierre"]]


@pytest.fixture(scope="module")
def dataset(tmp_path_factory: pytest.TempPathFactory) -> tg.DatasetResult:
    base = tmp_path_factory.mktemp("dataset")
    return tg.generate_dataset(SEED, N, base / "raw", base / "sample", SLA)


@pytest.fixture(scope="module")
def tickets(dataset: tg.DatasetResult) -> list[Row]:
    return _read(dataset.tickets_path)[1]


@pytest.fixture(scope="module")
def sucursales(dataset: tg.DatasetResult) -> dict[str, Row]:
    return {r["sucursal"]: r for r in _read(dataset.sucursales_path)[1]}


# --- Shape and determinism -------------------------------------------------------------


def test_writes_n_tickets_with_the_17_fields_in_order(dataset: tg.DatasetResult) -> None:
    header, rows = _read(dataset.tickets_path)
    assert header == list(tg.TICKET_FIELDS)
    assert len(tg.TICKET_FIELDS) == 17
    assert len(rows) == N == dataset.n_tickets


def test_ticket_ids_are_unique_and_follow_opening_order(tickets: list[Row]) -> None:
    ids = [r["ticket_id"] for r in tickets]
    assert len(set(ids)) == N
    assert ids == sorted(ids)
    openings = [r["fecha_apertura"] for r in tickets]
    assert openings == sorted(openings)


def test_same_seed_gives_identical_files(tmp_path: Path, dataset: tg.DatasetResult) -> None:
    again = tg.generate_dataset(SEED, N, tmp_path / "raw", tmp_path / "sample", SLA)
    assert _sha256(again.tickets_path) == _sha256(dataset.tickets_path)
    assert _sha256(again.sucursales_path) == _sha256(dataset.sucursales_path)
    assert _sha256(again.sample_path) == _sha256(dataset.sample_path)


def test_other_seed_gives_a_different_file(tmp_path: Path, dataset: tg.DatasetResult) -> None:
    other = tg.generate_dataset(SEED + 1, N, tmp_path / "raw", tmp_path / "sample", SLA)
    assert _sha256(other.tickets_path) != _sha256(dataset.tickets_path)


def test_generation_does_not_touch_the_global_random_state() -> None:
    import random

    random.seed(123)
    expected = random.random()
    random.seed(123)
    tg.generate_tickets(SEED, 50, SLA)
    assert random.random() == expected


@pytest.mark.parametrize("n", [0, -5])
def test_rejects_a_non_positive_ticket_count(n: int) -> None:
    with pytest.raises(ValueError, match="n must be"):
        tg.generate_tickets(SEED, n, SLA)


@pytest.mark.parametrize("sla", [{"P1": 4, "P2": 8, "P3": 24}, {**SLA, "P4": 0}])
def test_rejects_incomplete_or_invalid_sla(sla: dict[str, int]) -> None:
    with pytest.raises(ValueError, match="sla_horas"):
        tg.generate_tickets(SEED, 10, sla)


# --- Business patterns -----------------------------------------------------------------


def test_repetitive_share_is_between_35_and_45_percent(tickets: list[Row]) -> None:
    share = sum(r["es_repetitivo"] == "1" for r in tickets) / N
    assert 0.35 <= share <= 0.45


def test_repetitive_flag_matches_the_5_repetitive_subcategories(tickets: list[Row]) -> None:
    assert len(REPETITIVE_SUBCATEGORIES) == 5
    for row in tickets:
        assert row["es_repetitivo"] == (
            "1" if row["subcategoria"] in REPETITIVE_SUBCATEGORIES else "0"
        )


def test_unlock_tickets_peak_on_payday_days(tickets: list[Row]) -> None:
    days = [
        tg.PERIOD_START + timedelta(d) for d in range((tg.PERIOD_END - tg.PERIOD_START).days + 1)
    ]
    peak_days = [d for d in days if d.day in tg.QUINCENA_DAYS]
    unlocks = Counter(
        _dt(r["fecha_apertura"]).date()
        for r in tickets
        if r["subcategoria"] == tg.UNLOCK_SUBCATEGORY
    )
    peak_rate = sum(unlocks[d] for d in peak_days) / len(peak_days)
    rest_rate = sum(unlocks[d] for d in days if d.day not in tg.QUINCENA_DAYS) / (
        len(days) - len(peak_days)
    )
    assert peak_rate / rest_rate >= 1.5


def test_sla_compliance_is_at_least_10_pp_lower_in_foraneas(
    tickets: list[Row], sucursales: dict[str, Row]
) -> None:
    def compliance(foranea: str) -> float:
        rows = [r for r in _closed(tickets) if sucursales[r["sucursal"]]["es_foranea"] == foranea]
        return sum(r["sla_cumplido"] == "1" for r in rows) / len(rows)

    assert compliance("0") - compliance("1") >= 0.10


def test_priorities_use_the_configured_sla_hours(tickets: list[Row]) -> None:
    assert {r["prioridad"] for r in tickets} == set(SLA)
    for row in tickets:
        assert int(row["sla_horas"]) == SLA[row["prioridad"]]


def test_sla_hours_follow_a_custom_configuration() -> None:
    custom = {"P1": 2, "P2": 6, "P3": 12, "P4": 48}
    for ticket in tg.generate_tickets(SEED, 200, custom):
        assert ticket.sla_horas == custom[ticket.prioridad]


def test_about_10_percent_of_tickets_are_in_english(tickets: list[Row]) -> None:
    languages = Counter(r["idioma"] for r in tickets)
    assert set(languages) == {"es", "en"}
    assert 0.07 <= languages["en"] / N <= 0.13


def test_english_tickets_have_english_solutions(tickets: list[Row]) -> None:
    spanish = {r["solucion"] for r in tickets if r["idioma"] == "es"}
    english = {r["solucion"] for r in tickets if r["idioma"] == "en"}
    assert spanish.isdisjoint(english)
    assert all(" the " in f" {text.lower()}" for text in english)


def test_channels_are_the_four_expected_and_mixed(tickets: list[Row]) -> None:
    channels = Counter(r["canal"] for r in tickets)
    assert set(channels) == set(tg.CANALES) == {"portal", "correo", "teléfono", "Teams"}
    assert min(channels.values()) / N >= 0.05


def test_subcategories_cover_the_15_kb_topics_and_some_without_article(
    tickets: list[Row],
) -> None:
    used = {r["subcategoria"] for r in tickets}
    assert len(KB_SUBCATEGORIES) == 15
    assert set(KB_SUBCATEGORIES) <= used
    assert set(KB_SUBCATEGORIES) >= REPETITIVE_SUBCATEGORIES
    assert used - set(KB_SUBCATEGORIES), "expected subcategories without KB article (RN-06)"
    for topic in ("contraseña", "desbloqueo", "token", "vpn", "impresora", "sap", "correo"):
        assert any(topic in name.lower() for name in KB_SUBCATEGORIES), topic
    for topic in ("carpetas compartidas", "teams", "equipo lento"):
        assert any(topic in name.lower() for name in KB_SUBCATEGORIES), topic


def test_each_subcategory_belongs_to_a_single_category(tickets: list[Row]) -> None:
    pairs = {(r["subcategoria"], r["categoria"]) for r in tickets}
    assert len(pairs) == len({sub for sub, _ in pairs})
    assert {spec.categoria for spec in SUBCATEGORIES} >= {cat for _, cat in pairs}


def test_mandatory_escalations_say_so_in_the_solution(tickets: list[Row]) -> None:
    for row in tickets:
        if row["subcategoria"] in {"Sistema de caja", "Sospecha de fraude"}:
            assert row["solucion"].startswith(("Escalado a L2", "Escalated to L2"))


# --- Dates, states and SLA consistency -------------------------------------------------


def test_dates_fall_in_the_fixed_12_month_period(tickets: list[Row]) -> None:
    period = (tg.PERIOD_START, tg.PERIOD_END)
    assert period == (date(2025, 11, 1), date(2026, 10, 31))
    openings = [_dt(r["fecha_apertura"]).date() for r in tickets]
    assert min(openings) >= tg.PERIOD_START
    assert max(openings) <= tg.PERIOD_END
    assert len({r["anio_mes"] for r in tickets}) == 12


def test_anio_mes_matches_the_opening_date(tickets: list[Row]) -> None:
    for row in tickets:
        assert row["anio_mes"] == row["fecha_apertura"][:7]


def test_closed_tickets_have_consistent_close_date_and_hours(tickets: list[Row]) -> None:
    for row in _closed(tickets):
        opened, closed = _dt(row["fecha_apertura"]), _dt(row["fecha_cierre"])
        assert closed >= opened
        assert closed <= tg.REFERENCE_TIME
        hours = (closed - opened).total_seconds() / 3600
        assert float(row["horas_resolucion"]) == pytest.approx(hours, abs=0.005)
        assert float(row["horas_resolucion"]) > 0


def test_sla_cumplido_matches_hours_vs_sla(tickets: list[Row]) -> None:
    for row in _closed(tickets):
        met = float(row["horas_resolucion"]) <= int(row["sla_horas"])
        assert row["sla_cumplido"] == ("1" if met else "0")


def test_states_and_open_tickets_are_consistent(tickets: list[Row]) -> None:
    states = Counter(r["estado"] for r in tickets)
    assert set(states) <= set(tg.ESTADOS)
    assert states["cerrado"] > states["resuelto"] > 0
    open_rows = [r for r in tickets if r["estado"] in {"abierto", "en_proceso"}]
    assert open_rows, "recent tickets should still be open"
    for row in open_rows:
        assert row["fecha_cierre"] == row["horas_resolucion"] == row["sla_cumplido"] == ""
        assert _dt(row["fecha_apertura"]) >= tg.REFERENCE_TIME - timedelta(days=30)
    for row in tickets:
        if row["estado"] in {"resuelto", "cerrado"}:
            assert row["fecha_cierre"]


# --- Branch dimension ------------------------------------------------------------------


def test_sucursales_dimension_shape(dataset: tg.DatasetResult, sucursales: dict[str, Row]) -> None:
    header, rows = _read(dataset.sucursales_path)
    assert header == list(tg.SUCURSAL_FIELDS)
    assert len(rows) == len(sucursales) == dataset.n_sucursales
    assert 100 <= len(rows) <= 140
    assert len({r["ciudad"] for r in rows}) >= 30
    assert {r["ciudad"] for r in rows} >= set(METRO_CITIES)


def test_es_foranea_means_outside_the_three_metro_cities(sucursales: dict[str, Row]) -> None:
    for row in sucursales.values():
        assert row["es_foranea"] == ("0" if row["ciudad"] in METRO_CITIES else "1")
    assert {"0", "1"} == {r["es_foranea"] for r in sucursales.values()}


def test_every_ticket_joins_to_a_sucursal(tickets: list[Row], sucursales: dict[str, Row]) -> None:
    assert {r["sucursal"] for r in tickets} <= set(sucursales)


# --- Sample and summary ----------------------------------------------------------------


def test_sample_is_a_systematic_200_row_subset(
    dataset: tg.DatasetResult, tickets: list[Row]
) -> None:
    header, sample = _read(dataset.sample_path)
    assert header == list(tg.TICKET_FIELDS)
    assert len(sample) == tg.SAMPLE_SIZE == dataset.sample_size == 200
    step = N // tg.SAMPLE_SIZE
    assert sample == tickets[::step][: tg.SAMPLE_SIZE]
    share = sum(r["es_repetitivo"] == "1" for r in sample) / len(sample)
    assert 0.30 <= share <= 0.50


def test_sample_keeps_every_ticket_when_n_is_small() -> None:
    small = tg.generate_tickets(SEED, 50, SLA)
    assert tg.sample_tickets(small) == small


def test_pattern_stats_agree_with_the_files(dataset: tg.DatasetResult, tickets: list[Row]) -> None:
    stats = dataset.stats
    assert stats.repetitive_share == pytest.approx(
        sum(r["es_repetitivo"] == "1" for r in tickets) / N
    )
    assert stats.english_share == pytest.approx(sum(r["idioma"] == "en" for r in tickets) / N)
    assert stats.payday_unlock_ratio >= 1.5
    assert stats.sla_gap_pp >= 10
    assert stats.sla_metro_pct - stats.sla_foranea_pct == pytest.approx(stats.sla_gap_pp)
    assert stats.open_tickets == sum(r["fecha_cierre"] == "" for r in tickets)


def test_escalation_rates_follow_the_declared_bands() -> None:
    for spec in SUBCATEGORIES:
        if spec.name in {"Sistema de caja", "Sospecha de fraude"}:  # RN-03: always
            assert spec.escalation_rate == 1.0
        elif spec.repetitive:
            assert 0.05 <= spec.escalation_rate <= 0.12, spec.name
        elif spec.has_kb:
            assert 0.40 <= spec.escalation_rate <= 0.65, spec.name
        else:
            assert 0.70 <= spec.escalation_rate <= 0.90, spec.name
