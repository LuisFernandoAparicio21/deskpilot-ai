"""Helper scripts for the manual phase (T25); each one is also importable from tests."""

from __future__ import annotations

import io
import sys


def use_utf8_console() -> None:
    """Print ✓/✗ safely on Windows consoles whose code page is not UTF-8."""
    for stream in (sys.stdout, sys.stderr):
        if isinstance(stream, io.TextIOWrapper):
            stream.reconfigure(encoding="utf-8", errors="replace")
