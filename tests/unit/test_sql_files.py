"""Static checks of the 10 business queries in integrations/fabric/sql (S5, RF-20).

Portability SQLite <-> T-SQL (SQL analytics endpoint of Fabric) is checked twice:
1. sqlglot parses every file with ``read="tsql"`` and ``read="sqlite"`` using
   ``ErrorLevel.RAISE`` (collect every error and raise one ``ParseError``).
2. A list of forbidden patterns that one of the two engines does not support.
Execution on SQLite is covered by tests/integration/test_sql_queries.py.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
import sqlglot
from sqlglot import exp
from sqlglot.errors import ErrorLevel

from src.ingestion.ticket_catalog import ESCALATION_PREFIX, KB_SUBCATEGORIES
from src.utils.db import SQL_DIR, list_query_files

QUERY_FILES = list_query_files(SQL_DIR)

# Pattern -> why it is forbidden (checked on the SQL without comments, case-insensitive).
FORBIDDEN: dict[str, str] = {
    r"\bTOP\b": "T-SQL only; use ROW_NUMBER() in a CTE + WHERE rn <= N",
    r"\bLIMIT\b": "SQLite only; use ROW_NUMBER() in a CTE + WHERE rn <= N",
    r"\bOFFSET\b": "different syntax in each engine",
    r"\bstrftime\b": "SQLite only; use the precomputed anio_mes column",
    r"\bjulianday\b": "SQLite only; use the precomputed horas_resolucion column",
    r"\bDATEDIFF\b|\bDATEPART\b|\bGETDATE\b": "T-SQL only date functions",
    r"\|\|": "string concatenation differs (T-SQL uses +)",
    r"\bCONCAT\b": "not available in older SQLite versions",
    r"\bIFNULL\b|\bISNULL\b": "engine specific; use COALESCE",
    r"\bTRUE\b|\bFALSE\b": "boolean literals are not portable; flags are 0/1 integers",
    r'"': "double quotes are identifiers in T-SQL; strings use single quotes",
    r"\[": "bracket identifiers are T-SQL only",
    r"\bN'": "N'' literals are T-SQL only",
    r"\bdbo\.": "tables are referenced without schema",
}


def _without_comments(sql: str) -> str:
    return re.sub(r"--[^\n]*", "", sql)


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _tree(path: Path, dialect: str = "tsql") -> exp.Expr:
    statements = sqlglot.parse(_read(path), read=dialect, error_level=ErrorLevel.RAISE)
    assert len(statements) == 1, f"{path.name} must contain exactly one statement"
    tree = statements[0]
    assert tree is not None
    return tree


def test_there_are_ten_numbered_queries() -> None:
    assert [p.name[:3] for p in QUERY_FILES] == [f"{i:02d}_" for i in range(1, 11)]


@pytest.mark.parametrize("path", QUERY_FILES, ids=lambda p: p.stem)
@pytest.mark.parametrize("dialect", ["tsql", "sqlite"])
def test_parses_in_both_dialects(path: Path, dialect: str) -> None:
    _tree(path, dialect)


@pytest.mark.parametrize("path", QUERY_FILES, ids=lambda p: p.stem)
def test_no_forbidden_patterns(path: Path) -> None:
    sql = _without_comments(_read(path))
    found = {
        pattern: reason
        for pattern, reason in FORBIDDEN.items()
        if re.search(pattern, sql, re.IGNORECASE)
    }
    assert found == {}


@pytest.mark.parametrize("path", QUERY_FILES, ids=lambda p: p.stem)
def test_starts_with_business_comment(path: Path) -> None:
    sql = _read(path)
    assert sql.startswith("--")
    header = sql.split("WITH", 1)[0]
    for label in ("Pregunta de negocio:", "Técnica SQL:", "Cómo leer el resultado:"):
        assert label in header, f"{path.name} lacks '{label}'"


@pytest.mark.parametrize("path", QUERY_FILES, ids=lambda p: p.stem)
def test_only_the_final_select_has_order_by(path: Path) -> None:
    tree = _tree(path)
    orders = [o for o in tree.find_all(exp.Order) if not isinstance(o.parent, exp.Window)]
    assert all(o.parent is tree for o in orders), "ORDER BY outside the final SELECT"
    assert len(orders) <= 1


def test_queries_cover_join_group_by_cte_and_window_functions() -> None:
    trees = [_tree(p) for p in QUERY_FILES]

    def used(kind: type[exp.Expr]) -> bool:
        return any(t.find(kind) is not None for t in trees)

    windows = [w for t in trees for w in t.find_all(exp.Window)]
    window_kinds = {type(w.this) for w in windows}
    assert used(exp.Join)
    assert used(exp.Group)
    assert used(exp.CTE)
    assert {exp.RowNumber, exp.Rank, exp.Sum, exp.Lag} <= window_kinds


def test_ranking_uses_row_number_filter() -> None:
    sql = _without_comments(_read(SQL_DIR / "01_top_incidencias.sql"))
    assert "ROW_NUMBER()" in sql
    assert "WHERE posicion <= 10" in sql


def test_automatable_query_matches_catalog() -> None:
    sql = _read(next(p for p in QUERY_FILES if p.name.startswith("05_")))
    kb_cte = sql.split("WITH kb AS (", 1)[1].split(")", 1)[0]
    assert set(re.findall(r"SELECT '([^']+)'", kb_cte)) == set(KB_SUBCATEGORIES)
    for prefix in ESCALATION_PREFIX.values():
        assert f"NOT LIKE '{prefix.strip().rstrip('.')}%'" in sql
