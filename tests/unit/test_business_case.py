"""Business case audit (T23): every figure of docs/business-case.md is recomputed.

The seed-42 dataset is generated with the real generator and loader into a temp DB, the 10
cited SQL files are executed, and each value of the traceability table (section 10) is
compared with the recomputed one. Hours saved are re-derived arithmetically; eval metrics
are read from tests/eval/results.summary.json; ADR structure and references are checked.
Docs are never edited here: a mismatch fails with "doc vs recomputed".
"""

from __future__ import annotations

import json
import re
import sqlite3
from pathlib import Path

import pytest

from src.ingestion.sqlite_loader import load_sqlite
from src.ingestion.ticket_generator import generate_dataset
from src.utils.config import PROJECT_ROOT, load_settings
from src.utils.db import SQL_DIR, QueryResult, list_query_files, run_sql_file, sqlite_connection

DOC = PROJECT_ROOT / "docs" / "business-case.md"
ADR_DIR = PROJECT_ROOT / "docs" / "adr"
SUMMARY = PROJECT_ROOT / "tests" / "eval" / "results.summary.json"
NOTE = "Datos sintéticos generados para este proyecto; las cifras son ilustrativas"
REPETITIVE = (
    "Reseteo de contraseña",
    "Desbloqueo de usuario",
    "Token bancario",
    "Impresoras",
    "VPN",
)
Row = dict[str, object]


class Dataset:
    def __init__(self, db: Path, results: dict[str, QueryResult]) -> None:
        self.db = db
        self.results = results

    def rows(self, key: str) -> list[Row]:
        r = self.results[key]
        return [dict(zip(r.columns, row, strict=True)) for row in r.rows]

    def scalar(self, sql: str) -> float:
        conn = sqlite3.connect(self.db)
        try:
            value = conn.execute(sql).fetchone()[0]
        finally:
            conn.close()
        return float(value)


@pytest.fixture(scope="module")
def data(tmp_path_factory: pytest.TempPathFactory) -> Dataset:
    base = tmp_path_factory.mktemp("bc")
    settings = load_settings(env_file=base / "missing.env")
    assert settings.data.seed == 42
    assert settings.data.n_tickets == 5000
    generate_dataset(42, 5000, base / "raw", base / "sample", settings.sla_horas.model_dump())
    db = base / "deskpilot.db"
    load_sqlite(base / "raw", db)
    with sqlite_connection(db) as conn:
        results = {p.stem[:2]: run_sql_file(conn, p) for p in list_query_files(SQL_DIR)}
    return Dataset(db, results)


@pytest.fixture(scope="module")
def doc() -> str:
    return DOC.read_text(encoding="utf-8")


def _f(value: object) -> float:
    assert isinstance(value, int | float)
    return float(value)


def _table_rows(doc: str) -> dict[str, str]:
    section = doc.split("## 10. Trazabilidad", 1)[1].split("\n## ", 1)[0]
    rows: dict[str, str] = {}
    for line in section.splitlines():
        if line.startswith("|") and not line.startswith("| ---") and "Cifra" not in line:
            rows[line.split("|")[1].strip()] = line
    return rows


def _num(n: float) -> str:
    return f"{n:,.0f}"


def _by(rows: list[Row], key: str, value: str) -> Row:
    return next(r for r in rows if r[key] == value)


# ---------------------------------------------------------------- traceability


def test_traceability_table_has_every_expected_row(doc: str) -> None:
    labels = set(_table_rows(doc))
    expected = {
        "% repetitivo (5 subcategorías)",
        "% automatizable (RN-06)",
        "Factor quincena",
        "SLA local",
        "SLA foráneo",
        "% inglés",
        "Backlog",
        "Peor sucursal",
        "Horas ahorradas al mes",
        "Resultado de evaluación",
        "Tendencia mensual",
    }
    assert expected <= labels


def test_repetitive_share(data: Dataset, doc: str) -> None:
    total = data.scalar("SELECT COUNT(*) FROM tickets")
    assert total == 5000
    names = ",".join(f"'{n}'" for n in REPETITIVE)
    rep = data.scalar(f"SELECT COUNT(*) FROM tickets WHERE subcategoria IN ({names})")
    top = {r["subcategoria"]: r for r in data.rows("01")}
    # independent raw count must equal the cited query's top-10 counts
    assert rep == sum(_f(top[n]["tickets"]) for n in REPETITIVE)
    assert rep / total * 100 == pytest.approx(39.92, abs=0.005)
    assert rep == 1996
    row = _table_rows(doc)["% repetitivo (5 subcategorías)"]
    assert f"{_num(rep)} tickets, {rep / total * 100:.2f}%" in row
    pcts = sorted((_f(top[n]["pct_del_total"]) for n in REPETITIVE), reverse=True)
    assert pcts == [11.06, 10.08, 7.34, 5.78, 5.66]


def test_top5_cumulative_and_volumes(data: Dataset, doc: str) -> None:
    rows = data.rows("01")
    assert _f(rows[4]["pct_acumulado"]) == pytest.approx(40.92, abs=0.005)
    assert [int(_f(r["tickets"])) for r in rows[:5]] == [553, 504, 367, 328, 294]
    assert "40.92%" in _table_rows(doc)["Top 5 por volumen acumulado"]


def test_automatable_figures(data: Dataset, doc: str) -> None:
    rows = data.rows("05")
    auto = sum(_f(r["tickets_automatizables"]) for r in rows)
    pct = sum(_f(r["pct_del_banco"]) for r in rows)
    assert auto == 2562
    assert auto / 5000 * 100 == pytest.approx(51.24, abs=0.005)
    assert pct == pytest.approx(51.24, abs=0.03)
    assert f"2,562 tickets, {auto / 50:.2f}%" in _table_rows(doc)["% automatizable (RN-06)"]
    in_rep = sum(_f(_by(rows, "subcategoria", n)["tickets_automatizables"]) for n in REPETITIVE)
    assert in_rep == 1767
    assert in_rep / 1996 * 100 == pytest.approx(88.53, abs=0.005)
    assert "1,767 / 1,996 = 88.53%" in _table_rows(doc)["Automatizable dentro de las repetitivas"]
    # independent cross-check of RN-06 with raw SQL (not the CTE of the cited file)
    raw = data.scalar(
        "SELECT COUNT(*) FROM tickets WHERE estado IN ('resuelto','cerrado') "
        "AND solucion NOT LIKE 'Escalado a L2%' AND solucion NOT LIKE 'Escalated to L2%' "
        "AND subcategoria NOT IN ('Alta de usuario','Consulta general','Equipo dañado',"
        "'Red de sucursal','Sospecha de fraude')"
    )
    assert raw == auto


def test_best_subcategories_and_no_article(data: Dataset, doc: str) -> None:
    rows = data.rows("05")
    best = {
        "Desbloqueo de usuario": 91.27,
        "Reseteo de contraseña": 91.14,
        "Token bancario": 87.47,
        "Impresoras": 85.12,
        "VPN": 83.39,
    }
    for name, expected in best.items():
        got = _f(_by(rows, "subcategoria", name)["pct_automatizable"])
        assert got == pytest.approx(expected, abs=0.005), name
        assert f"{expected:.2f}%" in doc
    no_art = [r for r in rows if r["tiene_articulo"] == 0]
    assert len(no_art) == 5
    assert sum(_f(r["tickets"]) for r in no_art) == 689
    assert all(_f(r["tickets_automatizables"]) == 0 for r in no_art)
    caja = _by(rows, "subcategoria", "Sistema de caja")
    assert (caja["tickets"], caja["tickets_automatizables"]) == (224, 0)
    assert "224 tickets, 0 automatizables" in _table_rows(doc)["Sistema de caja"]
    assert "689 en 5 subcategorías" in _table_rows(doc)["Tickets sin artículo"]
    correo = _f(_by(rows, "subcategoria", "Correo")["pct_automatizable"])
    lento = _f(_by(rows, "subcategoria", "Equipo lento")["pct_automatizable"])
    assert correo == pytest.approx(41.16, abs=0.005)
    assert lento == pytest.approx(39.80, abs=0.005)


def test_hours_by_category(data: Dataset, doc: str) -> None:
    rows = data.rows("04")
    pct = {r["categoria"]: _f(r["pct_horas"]) for r in rows}
    assert pct["Accesos"] == pytest.approx(31.54, abs=0.005)
    assert pct["Hardware"] == pytest.approx(20.77, abs=0.005)
    assert pct["Comunicaciones"] == pytest.approx(18.78, abs=0.005)
    total = sum(_f(r["horas_totales"]) for r in rows)
    assert total == pytest.approx(114540.35, abs=0.5)
    row = _table_rows(doc)["Horas de resolución por categoría"]
    assert "Accesos 31.54%" in row and "114,540.35 h" in row


def test_quincena_factor(data: Dataset, doc: str) -> None:
    by = {r["tipo_dia"]: r for r in data.rows("07")}
    q, rest = by["quincena"], by["resto"]
    assert _f(q["desbloqueos_por_dia"]) == pytest.approx(2.30, abs=0.005)
    assert _f(rest["desbloqueos_por_dia"]) == pytest.approx(1.21, abs=0.005)
    factor = (_f(q["desbloqueos"]) / _f(q["dias"])) / (_f(rest["desbloqueos"]) / _f(rest["dias"]))
    assert factor == pytest.approx(1.90, abs=0.005)
    assert _f(q["veces_vs_resto"]) == pytest.approx(1.90, abs=0.005)
    assert (q["dias"], rest["dias"]) == (64, 296)
    assert _f(q["pct_desbloqueo"]) == pytest.approx(15.96, abs=0.005)
    assert _f(rest["pct_desbloqueo"]) == pytest.approx(8.75, abs=0.005)
    assert "1.90 (2.30 contra 1.21 por día)" in _table_rows(doc)["Factor quincena"]


def test_sla_local_vs_foranea_and_gap(data: Dataset, doc: str) -> None:
    by = {r["tipo_sucursal"]: _f(r["pct_sla_cumplido"]) for r in data.rows("08")}
    assert by["local"] == pytest.approx(79.50, abs=0.005)
    assert by["foranea"] == pytest.approx(60.57, abs=0.005)
    assert by["local"] - by["foranea"] == pytest.approx(18.93, abs=0.011)
    raw = data.scalar(
        "SELECT 100.0*SUM(t.sla_cumplido)/COUNT(*) FROM tickets t JOIN sucursales s "
        "ON s.sucursal=t.sucursal WHERE t.sla_cumplido IS NOT NULL AND s.es_foranea=1"
    )
    assert raw == pytest.approx(by["foranea"], abs=0.005)
    table = _table_rows(doc)
    assert "79.50%" in table["SLA local"]
    assert "60.57%" in table["SLA foráneo"] and "18.93 pp" in table["SLA foráneo"]


def test_worst_branch_and_area_sla(data: Dataset, doc: str) -> None:
    worst = next(r for r in data.rows("03") if r["posicion_peor"] == 1)
    assert worst["sucursal"] == "Puebla 05"
    assert _f(worst["pct_sla_cumplido"]) == pytest.approx(35.56, abs=0.005)
    assert "Puebla 05, 35.56%" in _table_rows(doc)["Peor sucursal"]
    areas = sorted(data.rows("02"), key=lambda r: _f(r["pct_sla_cumplido"]))
    assert areas[0]["area"] == "Caja"
    assert _f(areas[0]["pct_sla_cumplido"]) == pytest.approx(63.47, abs=0.005)
    assert _f(areas[0]["diferencia_pp"]) == pytest.approx(-4.50, abs=0.005)
    assert areas[-1]["area"] == "Cobranza"
    assert _f(areas[-1]["pct_sla_cumplido"]) == pytest.approx(71.65, abs=0.005)
    assert _f(areas[-1]["diferencia_pp"]) == pytest.approx(3.67, abs=0.005)
    assert "Caja 63.47% a Cobranza 71.65%" in _table_rows(doc)["SLA por área"]


def test_channels_and_english_share(data: Dataset, doc: str) -> None:
    rows = data.rows("09")
    pct = {str(r["canal"]).lower(): _f(r["pct_del_total"]) for r in rows}
    portal = next(v for k, v in pct.items() if "portal" in k)
    phone = next(v for k, v in pct.items() if "tel" in k)
    assert portal == pytest.approx(34.78, abs=0.005)
    assert phone == pytest.approx(26.40, abs=0.005)
    english = [int(_f(r["tickets_en_ingles"])) for r in rows]
    assert sorted(english, reverse=True) == [172, 123, 115, 71]
    assert sum(english) == 481
    assert sum(english) / 5000 * 100 == pytest.approx(9.62, abs=0.005)
    assert data.scalar("SELECT COUNT(*) FROM tickets WHERE idioma = 'en'") == 481
    assert "481 tickets, 9.62%" in _table_rows(doc)["% inglés"]


def test_backlog(data: Dataset, doc: str) -> None:
    backlog = {r["prioridad"]: int(_f(r["backlog"])) for r in data.rows("10")}
    assert backlog == {"P1": 0, "P2": 1, "P3": 7, "P4": 8}
    assert sum(backlog.values()) == 16
    raw = data.scalar("SELECT COUNT(*) FROM tickets WHERE estado IN ('abierto','en_proceso')")
    assert raw == 16
    assert "16 tickets (P1 0, P2 1, P3 7, P4 8)" in _table_rows(doc)["Backlog"]


def test_monthly_trend(data: Dataset, doc: str) -> None:
    rows = data.rows("06")
    counts = [int(_f(r["tickets"])) for r in rows]
    assert len(rows) == 12
    assert (min(counts), max(counts)) == (380, 453)
    assert sum(counts) == 5000
    assert rows[0]["anio_mes"] == "2025-11" and rows[-1]["anio_mes"] == "2026-10"
    sla = [_f(r["pct_sla_cumplido"]) for r in rows]
    assert min(sla) == pytest.approx(64.50, abs=0.005)
    assert max(sla) == pytest.approx(73.11, abs=0.005)
    assert "380 a 453 tickets al mes; 12 meses" in _table_rows(doc)["Tendencia mensual"]


# ------------------------------------------------------------------- hours


@pytest.mark.parametrize(
    ("minutes", "ceiling", "conservative", "scenario"),
    [(10, 35.6, 17.8, 427), (15, 53.4, 26.7, 641), (20, 71.2, 35.6, 854)],
)
def test_hours_saved_derive_from_tickets_and_minutes(
    data: Dataset, doc: str, minutes: int, ceiling: float, conservative: float, scenario: int
) -> None:
    auto = sum(_f(r["tickets_automatizables"]) for r in data.rows("05"))
    per_month = auto / len(data.rows("06"))
    assert per_month == pytest.approx(213.5)
    hours = per_month * minutes / 60
    assert hours == pytest.approx(ceiling, abs=0.05)
    assert hours / 2 == pytest.approx(conservative, abs=0.06)
    assert auto * minutes / 60 == pytest.approx(scenario, abs=0.5)  # 5,000 tickets/month case
    assert f"| {minutes} | {ceiling} | {conservative} |" in doc
    assert str(scenario) in doc


def test_minutes_are_declared_as_assumption(doc: str) -> None:
    assert "**SUPUESTO ILUSTRATIVO.** Minutos de trabajo" in doc
    assert "10, 15 o 20 minutos" in doc
    assert "35.6 / 53.4 / 71.2 h (10 / 15 / 20 min)" in _table_rows(doc)["Horas ahorradas al mes"]


# --------------------------------------------------------------- doc rules


def test_synthetic_note_exact_and_early(doc: str) -> None:
    assert NOTE in doc
    assert doc.index(NOTE) < doc.index("## 1. Contexto")


def test_every_cited_query_exists_and_all_are_cited(doc: str) -> None:
    cited = set(re.findall(r"`(\d{2}_[a-z_]+\.sql)`", doc))
    on_disk = {p.name for p in SQL_DIR.glob("[0-9][0-9]_*.sql")}
    assert len(on_disk) == 10
    assert cited and cited <= on_disk
    for name in on_disk:
        assert name in doc, f"{name} never cited"


# -------------------------------------------------------------------- eval


def test_eval_metrics_match_summary(doc: str) -> None:
    s = json.loads(SUMMARY.read_text(encoding="utf-8"))
    m = s["metrics"]
    assert (s["passed"], s["total"]) == (29, 30)
    assert (m["retrieval_top3"]["passed"], m["retrieval_top3"]["total"]) == (14, 14)
    assert (m["rechazo"]["passed"], m["rechazo"]["total"]) == (3, 4)
    assert (m["clasificacion"]["passed"], m["clasificacion"]["total"]) == (5, 5)
    assert (m["seguridad"]["passed"], m["seguridad"]["total"]) == (3, 3)
    assert m["aprobados"]["pct"] == pytest.approx(round(29 / 30 * 100, 1))
    assert [k for k, v in s["cases"].items() if v != "pasó"] == ["EV-16"]
    assert f"**{s['passed']} de {s['total']}** ({m['aprobados']['pct']}%)" in doc
    assert "**3 de 4 (75%)**" in doc and "EV-16" in doc
    assert f"p50 {s['latency_ms']['p50']} ms, p95 {s['latency_ms']['p95']} ms" in doc
    expected = f"29/30, rechazo 3/4, p95 {s['latency_ms']['p95']} ms"
    assert expected in _table_rows(doc)["Resultado de evaluación"]
    assert s["thresholds_met"] is False
    # Known failure EV-16 only => exit 3 per docs/features/eval-e2e.md.
    assert s["exit_code"] == 3
    assert f"sale con código {s['exit_code']}" in doc


# --------------------------------------------------------------------- ADRs

ADRS = sorted(ADR_DIR.glob("[0-9][0-9][0-9][0-9]-*.md"))


def test_adr_numbering_is_continuous_0001_to_0008() -> None:
    assert [p.name[:4] for p in ADRS] == [f"{i:04d}" for i in range(1, 9)]
    readme = (ADR_DIR / "README.md").read_text(encoding="utf-8")
    for p in ADRS:
        assert f"({p.name})" in readme


@pytest.mark.parametrize("path", ADRS, ids=lambda p: p.name[:4])
def test_adr_structure(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    assert text.startswith(f"# ADR-{path.name[:4]}:")
    assert "**Estado:**" in text
    headings = re.findall(r"^## (.+)$", text, re.MULTILINE)
    assert headings[:4] == ["Contexto", "Decisión", "Alternativas", "Consecuencias"]
    for h in headings[:4]:
        body = text.split(f"## {h}\n", 1)[1].split("\n## ", 1)[0]
        assert len(body.split()) >= 10, f"{path.name}: empty section {h}"


def _referenced_paths(text: str) -> set[str]:
    return set(
        re.findall(r"`((?:[\w.-]+/)+[\w.-]+\.(?:py|md|sql|yaml|yml|json|csv|toml|txt))`", text)
    )


@pytest.mark.parametrize("path", [*ADRS, DOC], ids=lambda p: p.name[:12])
def test_links_and_cited_paths_exist(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    broken: list[str] = []
    for target in re.findall(r"\]\(([^)#\s]+)(?:#[^)]*)?\)", text):
        if target.startswith(("http://", "https://", "mailto:")):
            continue
        if not (path.parent / target).resolve().exists():
            broken.append(target)
    for rel in _referenced_paths(text):
        if not any(c.exists() for c in (PROJECT_ROOT / rel, path.parent / rel)):
            broken.append(rel)
    assert broken == []


def test_adrs_cite_sources_file_that_exists() -> None:
    assert (PROJECT_ROOT / "docs" / "sources.md").is_file()
    citing = [p.name for p in ADRS if "docs/sources.md" in p.read_text(encoding="utf-8")]
    assert citing, "no ADR cites docs/sources.md"


def test_adr_latency_matches_eval() -> None:
    p95 = json.loads(SUMMARY.read_text(encoding="utf-8"))["latency_ms"]["p95"]
    text = (ADR_DIR / "0001-rag-extractivo-por-defecto.md").read_text(encoding="utf-8")
    assert f"{p95} ms" in text


# ------------------------------------------------------------- placeholders


@pytest.mark.parametrize("path", [DOC, *ADRS, ADR_DIR / "README.md"], ids=lambda p: p.name[:12])
def test_no_placeholders(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    found = re.findall(r"\bTODO\b|\bXXX+\b|lorem|ipsum|\bFIXME\b|\bTBD\b", text, re.IGNORECASE)
    assert found == []
