"""Static checks of the PySpark notebook that loads the Delta tables (S6, RF-23).

There is no Spark in CI, so the notebook is validated as nbformat JSON (with ``nbformat``
when installed, otherwise with an equivalent structural check) and every code cell is
compiled with ``ast.parse``. Running it in Spark is verified in Fabric (T29).
"""

from __future__ import annotations

import ast
import importlib
import json
import re
from pathlib import Path
from typing import Any

import pytest

from src.ingestion.ticket_generator import SUCURSAL_FIELDS, TICKET_FIELDS
from src.utils.config import PROJECT_ROOT

NOTEBOOK = PROJECT_ROOT / "integrations" / "fabric" / "notebooks" / "01_load_tickets_delta.ipynb"
CELL_ID = re.compile(r"^[a-zA-Z0-9_-]{1,64}$")


def _load(path: Path = NOTEBOOK) -> dict[str, Any]:
    data: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    return data


def _source(cell: dict[str, Any]) -> str:
    source = cell["source"]
    return source if isinstance(source, str) else "".join(source)


def _cells(kind: str) -> list[str]:
    return [_source(c) for c in _load()["cells"] if c["cell_type"] == kind]


def _code() -> str:
    return "\n".join(_cells("code"))


def _assigned_list(name: str) -> list[str]:
    for node in ast.walk(ast.parse(_code())):
        if isinstance(node, ast.Assign) and any(
            isinstance(t, ast.Name) and t.id == name for t in node.targets
        ):
            value: list[str] = ast.literal_eval(node.value)
            return value
    raise AssertionError(f"{name} is not assigned in the notebook")


def _check_structure(nb: dict[str, Any]) -> None:
    """Subset of the nbformat 4 schema, used when nbformat is not installed."""
    assert nb["nbformat"] == 4
    assert nb["nbformat_minor"] >= 4
    assert isinstance(nb["metadata"], dict)
    assert isinstance(nb["cells"], list) and nb["cells"]
    ids = []
    for cell in nb["cells"]:
        assert cell["cell_type"] in {"markdown", "code"}
        assert isinstance(cell["metadata"], dict)
        source = cell["source"]
        assert isinstance(source, str) or all(isinstance(line, str) for line in source)
        if nb["nbformat_minor"] >= 5:
            assert CELL_ID.match(cell["id"])
            ids.append(cell["id"])
        if cell["cell_type"] == "code":
            assert cell["outputs"] == [] and cell["execution_count"] is None
    assert len(ids) == len(set(ids))


def test_notebook_is_valid_nbformat() -> None:
    nb = _load()
    try:
        nbformat = importlib.import_module("nbformat")
    except ImportError:
        _check_structure(nb)
    else:  # pragma: no cover - nbformat is optional and not in requirements
        nbformat.validate(nbformat.reads(NOTEBOOK.read_text(encoding="utf-8"), as_version=4))
        _check_structure(nb)


def test_structure_check_rejects_broken_notebooks() -> None:
    broken = _load()
    first_code = next(c for c in broken["cells"] if c["cell_type"] == "code")
    first_code["outputs"] = [{"output_type": "stream", "text": "leaked"}]
    with pytest.raises(AssertionError):
        _check_structure(broken)


@pytest.mark.parametrize("index", range(len(_cells("code"))))
def test_every_code_cell_compiles(index: int) -> None:
    ast.parse(_cells("code")[index], filename=f"{NOTEBOOK.name}#code{index}")


def test_markdown_explains_each_step_in_spanish() -> None:
    cells = _load()["cells"]
    assert cells[0]["cell_type"] == "markdown"
    for previous, cell in zip(cells, cells[1:], strict=False):
        if cell["cell_type"] == "code":
            assert previous["cell_type"] == "markdown", "every code cell needs an explanation"
    text = "\n".join(_cells("markdown"))
    for phrase in ("Qué hace", "lakehouse", "Files/raw/", "Chequeos de calidad", "Verificación"):
        assert phrase in text
    assert "⚠ No verificado en Spark" in text and "T29" in text


def test_columns_match_the_generator() -> None:
    assert tuple(_assigned_list("TICKET_COLUMNS")) == TICKET_FIELDS
    assert tuple(_assigned_list("SUCURSAL_COLUMNS")) == SUCURSAL_FIELDS


def test_reads_raw_files_with_explicit_schema() -> None:
    code = _code()
    assert 'RAW_DIR = "Files/raw"' in code
    assert "/tickets.csv" in code and "/sucursales.csv" in code
    assert ".schema(raw_schema(columns))" in code
    assert "inferSchema" not in code


@pytest.mark.parametrize(
    "snippet",
    [
        'F.to_timestamp("fecha_apertura", TIMESTAMP_FORMAT)',
        'F.to_timestamp("fecha_cierre", TIMESTAMP_FORMAT)',
        'F.col("sla_cumplido").cast("int")',
        'F.col("es_repetitivo").cast("int")',
        'F.col("es_foranea").cast("int")',
        'F.col("horas_resolucion").cast("double")',
        'dropDuplicates(["ticket_id"])',
        "F.trim(",
    ],
)
def test_cleaning_steps(snippet: str) -> None:
    assert snippet in _code()


def test_quality_checks_cover_counts_null_keys_and_date_range() -> None:
    code = _code()
    for snippet in (".count()", "isNull()", "PERIOD_START", "PERIOD_END", "left_anti"):
        assert snippet in code


def test_writes_delta_tables_with_overwrite() -> None:
    code = _code()
    for table in ("tickets", "sucursales"):
        assert f'.write.mode("overwrite").format("delta").saveAsTable("{table}")' in code


def test_last_cell_verifies_counts_with_spark_sql() -> None:
    last = _cells("code")[-1]
    assert 'spark.sql(f"SELECT COUNT(*)' in last


def test_no_secrets_or_absolute_paths() -> None:
    raw = NOTEBOOK.read_text(encoding="utf-8").lower()
    for forbidden in ("azure_client_secret", "password", "abfss://", "c:\\\\", "token"):
        assert forbidden not in raw
