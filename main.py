"""Command-line entry point for DeskPilot AI.

Every pipeline step runs through a subcommand:

    python main.py generate-data | load-db | index | serve | eval | export-openapi

In the base scaffold (T3) each subcommand only reports which task will implement it
and exits with code 2. Later tasks replace the placeholders with real handlers.
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence

EXIT_NOT_IMPLEMENTED = 2

# Subcommand -> (help text, task that implements it).
SUBCOMMANDS: dict[str, tuple[str, str]] = {
    "generate-data": ("Generate the synthetic ticket dataset (seeded).", "T9"),
    "load-db": ("Load the generated tickets into the local SQLite database.", "T10"),
    "index": ("Chunk, embed and index the knowledge base into the vector database.", "T14"),
    "serve": ("Start the FastAPI service.", "T16"),
    "eval": ("Run the agent evaluation cases and save the results.", "T21"),
    "export-openapi": ("Export the OpenAPI spec for Copilot Studio.", "T19"),
}


def build_parser() -> argparse.ArgumentParser:
    """Build the CLI parser with one subparser per pipeline step."""
    parser = argparse.ArgumentParser(
        prog="deskpilot",
        description="DeskPilot AI: RAG-based L1 service desk assistant (synthetic data).",
    )
    subparsers = parser.add_subparsers(dest="command", required=True, metavar="COMMAND")
    for name, (help_text, _task) in SUBCOMMANDS.items():
        subparsers.add_parser(name, help=help_text, description=help_text)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Parse ``argv`` and dispatch the selected subcommand; return the process exit code."""
    args = build_parser().parse_args(argv)
    command: str = args.command
    _help_text, task = SUBCOMMANDS[command]
    print(f"{command}: not implemented yet ({task})", file=sys.stderr)
    return EXIT_NOT_IMPLEMENTED


if __name__ == "__main__":
    sys.exit(main())
