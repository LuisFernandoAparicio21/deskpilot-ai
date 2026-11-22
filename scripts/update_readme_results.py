"""Refresh the generated results block of README.md from the evaluation output (S12, T25).

Run from the repo root::

    .venv\\Scripts\\python -m scripts.update_readme_results [--check] [--dry-run]

Reads ``tests/eval/results.summary.json`` (written by ``python main.py eval``) and, when
they exist, the Copilot Studio results of the T32 table in docs/testing-procedure.md
(columns ``ID`` and ``Pasó (sí/no)``; cells still saying PENDIENTE are not counted).
Only the text between ``<!-- RESULTS:START -->`` and ``<!-- RESULTS:END -->`` in README.md
is replaced; everything else is left untouched. The script is idempotent: a second run
changes nothing.

When README.md has them, two more blocks are rendered from ``docs/validation-status.json``
(``--status`` overrides it): ``<!-- VALIDATION:START/END -->`` (integration status table) and
``<!-- MSBADGES:START/END -->`` (Copilot Studio and Fabric badges, green only if ``validado``
with date and evidence). Each pair must be unique with START before END; a README with
neither pair skips both blocks.

Options: ``--check`` writes nothing and exits 1 if the README block is out of date;
``--dry-run`` prints the block that would be written and changes nothing.

Exit codes: 0 = README up to date or updated (or --dry-run); 1 = --check found the README
out of date; 2 = bad input (missing or invalid summary, markers missing in the README).
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Callable, Sequence
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import quote

from scripts import use_utf8_console
from src.utils.config import PROJECT_ROOT

EXIT_OK = 0
EXIT_OUTDATED = 1
EXIT_BAD_INPUT = 2

START = "<!-- RESULTS:START -->"
END = "<!-- RESULTS:END -->"
SUMMARY_PATH = PROJECT_ROOT / "tests" / "eval" / "results.summary.json"
README_PATH = PROJECT_ROOT / "README.md"
STATUS_PATH = PROJECT_ROOT / "docs" / "validation-status.json"
VALIDATION_START = "<!-- VALIDATION:START -->"
VALIDATION_END = "<!-- VALIDATION:END -->"
BADGES_START = "<!-- MSBADGES:START -->"
BADGES_END = "<!-- MSBADGES:END -->"
INTEGRATION_IDS = ("fabric", "copilot_studio", "power_bi", "video")
STATUS_FIELDS = {"id", "nombre", "estado", "fecha", "evidencia", "que_falta"}
BADGES = {"copilot_studio": "Copilot Studio", "fabric": "Fabric"}
TESTING_PATH = PROJECT_ROOT / "docs" / "testing-procedure.md"
T32_HEADING = "## Resultados en Copilot Studio (T32)"

METRIC_LABELS = {
    "aprobados": "Cases passed",
    "retrieval_top3": "Top-3 retrieval",
    "rechazo": "Correct refusal",
    "clasificacion": "Ticket classification",
    "seguridad": "Security",
}


class InputError(Exception):
    """An input file is missing, invalid or lacks the markers; the message says how to fix."""


def load_summary(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise InputError(
            f"cannot read {path} ({type(exc).__name__}). Run: python main.py eval"
        ) from exc
    except ValueError as exc:
        raise InputError(f"{path} is not valid JSON. Run again: python main.py eval") from exc
    if not isinstance(data, dict) or not {"metrics", "latency_ms", "total"} <= data.keys():
        raise InputError(f"{path} lacks metrics/latency_ms/total. Run again: python main.py eval")
    problem = _schema_problem(data)
    if problem:
        raise InputError(f"{path} is malformed ({problem}). Run again: python main.py eval")
    return data


def _is_number(value: Any) -> bool:
    return isinstance(value, int | float) and not isinstance(value, bool)


METRIC_FIELDS: dict[str, Callable[[Any], bool]] = {
    "passed": _is_number,
    "total": _is_number,
    "pct": _is_number,
    "threshold_pct": _is_number,
    "met": lambda v: isinstance(v, bool),
}


def _schema_problem(data: dict[str, Any]) -> str | None:
    """First schema violation in the summary, or None. Values are never echoed."""
    metrics, latency = data["metrics"], data["latency_ms"]
    if not isinstance(metrics, dict):
        return "metrics must be an object"
    for key, m in metrics.items():
        if key not in METRIC_LABELS:
            continue
        if not isinstance(m, dict):
            return f"metrics.{key} must be an object"
        for field, check in METRIC_FIELDS.items():
            if field not in m:
                return f"metrics.{key} lacks '{field}'"
            if not check(m[field]):
                return f"metrics.{key}.{field} has the wrong type"
    if not isinstance(latency, dict):
        return "latency_ms must be an object"
    for field in ("p50", "p95"):
        if field not in latency:
            return f"latency_ms lacks '{field}'"
        if not _is_number(latency[field]):
            return f"latency_ms.{field} has the wrong type"
    if not (_is_number(data["total"])):
        return "total must be a number"
    cases = data.get("cases", {})
    if not isinstance(cases, dict):
        return "cases must be an object"
    return None


def read_copilot_results(path: Path) -> tuple[int, int] | None:
    """(passed, answered) from the T32 table, or None if absent or still all PENDIENTE."""
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return None
    try:
        start = lines.index(T32_HEADING)
    except ValueError:
        return None
    column: int | None = None
    passed = answered = 0
    for line in lines[start + 1 :]:
        if line.startswith("## "):
            break
        if not line.startswith("|"):
            continue
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if column is None:
            column = next((i for i, c in enumerate(cells) if c.lower().startswith("pas")), None)
            continue
        if column >= len(cells) or cells[0].startswith("---"):
            continue
        verdict = cells[column].lower()
        if verdict in {"sí", "si"}:
            passed += 1
            answered += 1
        elif verdict == "no":
            answered += 1
    return (passed, answered) if answered else None


def render_block(summary: dict[str, Any], copilot: tuple[int, int] | None) -> str:
    """The generated Markdown (``\\n`` line ends), without the markers."""
    day = str(summary.get("generated_at", ""))[:10]
    try:
        datetime.strptime(day, "%Y-%m-%d")
    except ValueError:
        day = "unknown date"
    lines = [
        f"Local evaluation of {summary['total']} cases (backend `{summary.get('backend', '?')}`,"
        f" {day}), generated from `tests/eval/results.summary.json`:",
        "",
        "| Metric | Result | Threshold | Met |",
        "| --- | --- | --- | --- |",
    ]
    metrics: dict[str, Any] = summary["metrics"]
    for key, label in METRIC_LABELS.items():
        m = metrics.get(key)
        if m is None:
            continue
        mark = "yes" if m["met"] else "no"
        lines.append(
            f"| {label} | {m['passed']}/{m['total']} ({m['pct']}%) | "
            f">= {m['threshold_pct']}% | {mark} |"
        )
    latency = summary["latency_ms"]
    lines.append(
        f"| Latency per case | p50 {latency['p50']} ms, p95 {latency['p95']} ms | - | - |"
    )
    failed = sorted(k for k, v in summary.get("cases", {}).items() if v != "pasó")
    lines += ["", f"Failed cases: {', '.join(failed) if failed else 'none'}.", ""]
    if copilot is None:
        lines.append(
            "Copilot Studio: **pending (manual)**, no measured results yet "
            "([`docs/testing-procedure.md`](docs/testing-procedure.md), T32)."
        )
    else:
        passed, answered = copilot
        lines.append(
            f"Copilot Studio (T32, measured by hand): {passed} of {answered} answered cases "
            "passed ([`docs/testing-procedure.md`](docs/testing-procedure.md))."
        )
    return "\n".join(lines)


def _text(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _status_problem(data: Any) -> str | None:
    """First schema violation in validation-status.json, or None."""
    if not isinstance(data, list):
        return "must be a list of integrations"
    seen: list[str] = []
    for i, item in enumerate(data):
        if not isinstance(item, dict):
            return f"item {i} must be an object"
        if item.keys() != STATUS_FIELDS:
            return f"item {i} must have exactly the fields {sorted(STATUS_FIELDS)}"
        name = item["id"]
        if name not in INTEGRATION_IDS:
            return f"item {i} has an unknown id (allowed: {', '.join(INTEGRATION_IDS)})"
        if name in seen:
            return f"id '{name}' is repeated"
        seen.append(name)
        if not _text(item["nombre"]) or not _text(item["que_falta"]):
            return f"'{name}': nombre and que_falta must be non-empty text"
        if item["estado"] == "validado":
            if not _text(item["fecha"]) or not _text(item["evidencia"]):
                return f"'{name}' is validado: fecha and evidencia must not be null"
            try:
                datetime.strptime(item["fecha"], "%Y-%m-%d")
            except ValueError:
                return f"'{name}': fecha must be YYYY-MM-DD"
        elif item["estado"] == "pendiente":
            if item["fecha"] is not None or item["evidencia"] is not None:
                return f"'{name}' is pendiente: fecha and evidencia must be null"
        else:
            return f"'{name}': estado must be 'pendiente' or 'validado'"
    missing = [k for k in INTEGRATION_IDS if k not in seen]
    return f"missing integrations: {', '.join(missing)}" if missing else None


def load_status(path: Path) -> list[dict[str, Any]]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise InputError(f"cannot read {path} ({type(exc).__name__})") from exc
    except ValueError as exc:
        raise InputError(f"{path} is not valid JSON") from exc
    problem = _status_problem(data)
    if problem:
        raise InputError(f"{path} is invalid: {problem}")
    return list(data)


def render_validation(status: list[dict[str, Any]]) -> str:
    lines = [
        "| Integration | Status | Evidence | What is missing |",
        "| --- | --- | --- | --- |",
    ]
    for item in status:
        if item["estado"] == "validado":
            mark = f"✅ Validated ({item['fecha']})"
            evidence = f"[{item['evidencia']}]({item['evidencia']})"
        else:
            mark, evidence = "⏳ Pending validation on a real tenant", "-"
        lines.append(f"| {item['nombre']} | {mark} | {evidence} | {item['que_falta']} |")
    return "\n".join(lines)


def render_badges(status: list[dict[str, Any]]) -> str:
    by_id = {item["id"]: item for item in status}
    lines = []
    for key, label in BADGES.items():
        item = by_id[key]
        if item["estado"] == "validado":
            text, color, alt = "validated", "2EA043", f"{label}: validated on {item['fecha']}"
        else:
            text = "pending validation on a real tenant"
            color, alt = "6B7280", f"{label}: {text}"
        url = (
            f"https://img.shields.io/badge/{quote(label)}-{quote(text)}-{color}?style=for-the-badge"
        )
        lines.append(f"![{alt}]({url})")
    return "\n".join(lines)


def _replace_pair(text: str, start_marker: str, end_marker: str, block: str) -> str:
    start, end = text.find(start_marker), text.find(end_marker)
    if text.count(start_marker) != 1 or text.count(end_marker) != 1 or end < start:
        raise InputError(
            f"README.md needs exactly one {start_marker} ... {end_marker} pair "
            "(START before END). Add them where the generated block should show."
        )
    eol = "\r\n" if "\r\n" in text else "\n"
    body = block.replace("\n", eol)
    return f"{text[: start + len(start_marker)]}{eol}{body}{eol}{text[end:]}"


def replace_block(readme: str, block: str) -> str:
    """Return ``readme`` with the marked block replaced; keeps the file's line endings."""
    return _replace_pair(readme, START, END, block)


def apply_status_blocks(text: str, status_path: Path) -> tuple[str, list[str]]:
    """Fill the optional VALIDATION and MSBADGES pairs; a README without them skips them."""
    pairs = (
        (VALIDATION_START, VALIDATION_END, render_validation),
        (BADGES_START, BADGES_END, render_badges),
    )
    wanted = [p for p in pairs if p[0] in text or p[1] in text]
    if not wanted:
        return text, []
    status = load_status(status_path)
    rendered: list[str] = []
    for start, end, render in wanted:
        block = render(status)
        text = _replace_pair(text, start, end, block)
        rendered.append(block)
    return text, rendered


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Update the generated results block of README.md (idempotent).",
        epilog="Exit codes: 0 ok, 1 --check found the README out of date, 2 bad input.",
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--check", action="store_true", help="write nothing; exit 1 if the README is out of date"
    )
    mode.add_argument("--dry-run", action="store_true", help="print the block; write nothing")
    parser.add_argument("--summary", type=Path, default=SUMMARY_PATH, help="results.summary.json")
    parser.add_argument("--readme", type=Path, default=README_PATH, help="README to update")
    parser.add_argument("--status", type=Path, default=STATUS_PATH, help="validation-status.json")
    parser.add_argument("--testing-doc", type=Path, default=TESTING_PATH, help="T32 table source")
    return parser


def run(args: argparse.Namespace) -> int:
    try:
        summary = load_summary(args.summary)
        block = render_block(summary, read_copilot_results(args.testing_doc))
        with args.readme.open(encoding="utf-8", newline="") as handle:
            current = handle.read()
        updated = replace_block(current, block)
        updated, extra = apply_status_blocks(updated, args.status)
        block = "\n\n".join([block, *extra])
    except InputError as exc:
        print(f"✗ {exc}")
        return EXIT_BAD_INPUT
    except OSError as exc:
        print(f"✗ cannot read {args.readme} ({type(exc).__name__})")
        return EXIT_BAD_INPUT
    if args.dry_run:
        print(block)
        print(f"- dry run: {'README would change' if updated != current else 'no changes'}")
        return EXIT_OK
    if updated == current:
        print("✓ README results block is up to date")
        return EXIT_OK
    if args.check:
        print("✗ README results block is out of date")
        print("  What to do: run `python -m scripts.update_readme_results` and commit README.md")
        return EXIT_OUTDATED
    with args.readme.open("w", encoding="utf-8", newline="") as handle:
        handle.write(updated)
    print("✓ README results block updated")
    return EXIT_OK


def main(argv: Sequence[str] | None = None) -> int:
    return run(build_parser().parse_args(argv))


if __name__ == "__main__":
    use_utf8_console()
    sys.exit(main())
