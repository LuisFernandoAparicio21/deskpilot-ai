"""Refresh the generated results block of README.md from the evaluation output (S12, T25).

Run from the repo root::

    .venv\\Scripts\\python -m scripts.update_readme_results [--check] [--dry-run]

Reads ``tests/eval/results.summary.json`` (written by ``python main.py eval``) and, when
they exist, the Copilot Studio results of the T32 table in docs/testing-procedure.md
(columns ``ID`` and ``Pasó (sí/no)``; cells still saying PENDIENTE are not counted).
Only the text between ``<!-- RESULTS:START -->`` and ``<!-- RESULTS:END -->`` in README.md
is replaced; everything else is left untouched. The script is idempotent: a second run
changes nothing.

Options: ``--check`` writes nothing and exits 1 if the README block is out of date;
``--dry-run`` prints the block that would be written and changes nothing.

Exit codes: 0 = README up to date or updated (or --dry-run); 1 = --check found the README
out of date; 2 = bad input (missing or invalid summary, markers missing in the README).
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from datetime import datetime
from pathlib import Path
from typing import Any

from scripts import use_utf8_console
from src.utils.config import PROJECT_ROOT

EXIT_OK = 0
EXIT_OUTDATED = 1
EXIT_BAD_INPUT = 2

START = "<!-- RESULTS:START -->"
END = "<!-- RESULTS:END -->"
SUMMARY_PATH = PROJECT_ROOT / "tests" / "eval" / "results.summary.json"
README_PATH = PROJECT_ROOT / "README.md"
TESTING_PATH = PROJECT_ROOT / "docs" / "testing-procedure.md"
T32_HEADING = "## Resultados en Copilot Studio (T32)"

METRIC_LABELS = {
    "aprobados": "Casos aprobados",
    "retrieval_top3": "Recuperación top-3",
    "rechazo": "Rechazo correcto",
    "clasificacion": "Clasificación de tickets",
    "seguridad": "Seguridad",
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
    return data


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
        day = "fecha desconocida"
    lines = [
        f"Evaluación local de {summary['total']} casos (backend `{summary.get('backend', '?')}`,"
        f" {day}), generada desde `tests/eval/results.summary.json`:",
        "",
        "| Métrica | Resultado | Umbral | Cumple |",
        "| --- | --- | --- | --- |",
    ]
    metrics: dict[str, Any] = summary["metrics"]
    for key, label in METRIC_LABELS.items():
        m = metrics.get(key)
        if m is None:
            continue
        mark = "sí" if m["met"] else "no"
        lines.append(
            f"| {label} | {m['passed']}/{m['total']} ({m['pct']}%) | "
            f">= {m['threshold_pct']}% | {mark} |"
        )
    latency = summary["latency_ms"]
    lines.append(
        f"| Latencia por caso | p50 {latency['p50']} ms, p95 {latency['p95']} ms | - | - |"
    )
    failed = sorted(k for k, v in summary.get("cases", {}).items() if v != "pasó")
    lines += ["", f"Casos fallidos: {', '.join(failed) if failed else 'ninguno'}.", ""]
    if copilot is None:
        lines.append(
            "Copilot Studio: **pendiente (manual)**, sin resultados medidos todavía "
            "([`docs/testing-procedure.md`](docs/testing-procedure.md), T32)."
        )
    else:
        passed, answered = copilot
        lines.append(
            f"Copilot Studio (T32, medido a mano): {passed} de {answered} casos respondidos "
            "pasaron ([`docs/testing-procedure.md`](docs/testing-procedure.md))."
        )
    return "\n".join(lines)


def replace_block(readme: str, block: str) -> str:
    """Return ``readme`` with the marked block replaced; keeps the file's line endings."""
    start, end = readme.find(START), readme.find(END)
    if start == -1 or end == -1 or end < start or readme.count(START) != 1:
        raise InputError(
            f"README.md needs exactly one {START} ... {END} pair (START before END). "
            "Add them where the results section should show the generated block."
        )
    eol = "\r\n" if "\r\n" in readme else "\n"
    body = block.replace("\n", eol)
    return f"{readme[: start + len(START)]}{eol}{body}{eol}{readme[end:]}"


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
    parser.add_argument("--testing-doc", type=Path, default=TESTING_PATH, help="T32 table source")
    return parser


def run(args: argparse.Namespace) -> int:
    try:
        summary = load_summary(args.summary)
        block = render_block(summary, read_copilot_results(args.testing_doc))
        with args.readme.open(encoding="utf-8", newline="") as handle:
            current = handle.read()
        updated = replace_block(current, block)
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
        print("  Qué hacer: run `python -m scripts.update_readme_results` and commit README.md")
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
