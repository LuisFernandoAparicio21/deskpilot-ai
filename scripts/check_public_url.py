"""Check that the public HTTPS URL of the API is ready for Copilot Studio (S8, S16, T25).

Run from the repo root::

    .venv\\Scripts\\python -m scripts.check_public_url https://<host> [--api-key-env NAME]

Checks, in order:

1. the URL uses https (``--allow-http`` downgrades this to a warning, local tests only);
2. ``GET /health`` answers 200;
3. ``POST /buscar_solucion`` without a key answers 401;
4. ``POST /buscar_solucion`` with the key answers 200 with citations, in Spanish and
   in English;
5. ``/docs``, ``/redoc`` and ``/openapi.json`` are off (404);
6. the ``host`` of integrations/copilot_studio/openapi.json matches the URL (warning only);
7. latency of every request stays under ``--max-latency-ms`` (warning only); a timeout
   (``--timeout``) is a failure.

The API key is read from the environment variable named by ``--api-key-env`` (default
DESKPILOT_API_KEY) or from .env, and is never printed.

Exit codes: 0 = every check passed (warnings allowed); 1 = a check failed (including a
non-https URL); 2 = bad usage (invalid URL, key variable not set).
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

import httpx
from dotenv import dotenv_values

from scripts import use_utf8_console
from src.utils.config import DEFAULT_ENV_FILE, PROJECT_ROOT

EXIT_OK = 0
EXIT_CHECK_FAILED = 1
EXIT_USAGE = 2

MANUAL = "docs/MANUAL_STEPS.md"
OPENAPI_PATH = PROJECT_ROOT / "integrations" / "copilot_studio" / "openapi.json"
PLACEHOLDER_HOST = "your-deskpilot-host.example.com"
QUERIES = {
    "es": "La VPN no conecta cuando trabajo desde casa.",
    "en": "The printer is offline and my documents are stuck in the print queue.",
}
HIDDEN_PATHS = ("/docs", "/redoc", "/openapi.json")


@dataclass
class Report:
    failures: int = 0
    warnings: int = 0
    latencies: list[tuple[str, float]] = field(default_factory=list)

    def ok(self, message: str) -> None:
        print(f"✓ {message}")

    def warn(self, message: str, hint: str) -> None:
        self.warnings += 1
        print(f"⚠ {message}")
        print(f"  Qué hacer: {hint}")

    def fail(self, message: str, hint: str) -> None:
        self.failures += 1
        print(f"✗ {message}")
        print(f"  Qué hacer: {hint}")


def _request(
    client: httpx.Client, report: Report, label: str, method: str, path: str, **kwargs: Any
) -> httpx.Response | None:
    """One request; records latency. A timeout or network error is reported, not raised."""
    start = time.perf_counter()
    try:
        response = client.request(method, path, **kwargs)
    except httpx.TimeoutException:
        report.fail(
            f"{label}: timed out after {client.timeout.read}s",
            "check that the tunnel and `python main.py serve` are running; "
            "raise --timeout if the first call is slow (cold start).",
        )
        return None
    except httpx.HTTPError as exc:  # only the type: URLs and headers stay out of the output
        report.fail(
            f"{label}: connection error ({type(exc).__name__})",
            f"check the URL, that the tunnel is up and the API is running; see {MANUAL}.",
        )
        return None
    report.latencies.append((label, (time.perf_counter() - start) * 1000))
    return response


def _json(response: httpx.Response) -> dict[str, Any]:
    try:
        data = response.json()
    except ValueError:
        return {}
    return data if isinstance(data, dict) else {}


def check_scheme(url: str, allow_http: bool, report: Report) -> bool:
    scheme = urlsplit(url).scheme
    if scheme == "https":
        report.ok("URL uses https")
        return True
    if scheme == "http" and allow_http:
        report.warn(
            "URL uses http (--allow-http): fine for local tests, never for Copilot Studio",
            "use the https URL of the tunnel for the real check.",
        )
        return True
    report.fail(
        f"URL scheme is '{scheme or 'none'}', https is required",
        "use the https URL of your tunnel (see docs/research/public-https-url-options.md); "
        "for a local server on http pass --allow-http.",
    )
    return False


def check_health(client: httpx.Client, report: Report) -> None:
    response = _request(client, report, "GET /health", "GET", "/health")
    if response is None:
        return
    if response.status_code == 200:
        status = _json(response).get("status")
        report.ok(f"GET /health -> 200 (status={status!r})")
    else:
        report.fail(
            f"GET /health -> {response.status_code}, expected 200",
            "the URL does not reach DeskPilot: check the tunnel target port (8000) and "
            "that `python main.py serve` is running.",
        )


def check_auth_required(client: httpx.Client, report: Report) -> None:
    response = _request(
        client, report, "POST /buscar_solucion (no key)", "POST", "/buscar_solucion",
        json={"query": QUERIES["es"]},
    )  # fmt: skip
    if response is None:
        return
    if response.status_code == 401:
        report.ok("POST /buscar_solucion without a key -> 401")
    else:
        report.fail(
            f"POST /buscar_solucion without a key -> {response.status_code}, expected 401",
            "the API must require X-API-Key; if a proxy answers instead, check the tunnel.",
        )


def check_search(client: httpx.Client, api_key: str, report: Report) -> None:
    for lang, query in QUERIES.items():
        label = f"POST /buscar_solucion ({lang})"
        response = _request(
            client, report, label, "POST", "/buscar_solucion",
            json={"query": query}, headers={"X-API-Key": api_key},
        )  # fmt: skip
        if response is None:
            continue
        body = _json(response)
        if response.status_code == 401:
            report.fail(
                f"{label} -> 401: the key was rejected",
                "the key in your environment must equal the DESKPILOT_API_KEY of the "
                "running server.",
            )
        elif response.status_code != 200:
            report.fail(
                f"{label} -> {response.status_code}, expected 200",
                "check the server log (logs/) and that `python main.py index` was run.",
            )
        elif not body.get("citations"):
            report.fail(
                f"{label} -> 200 without citations (status={body.get('status')!r})",
                "the vector index may be empty: run `python main.py index`.",
            )
        else:
            count = len(body["citations"])
            report.ok(f"{label} -> 200, status={body.get('status')!r}, {count} citation(s)")


def check_hidden_docs(client: httpx.Client, report: Report) -> None:
    for path in HIDDEN_PATHS:
        response = _request(client, report, f"GET {path}", "GET", path)
        if response is None:
            continue
        if response.status_code == 404:
            report.ok(f"GET {path} -> 404 (off)")
        else:
            report.fail(
                f"GET {path} -> {response.status_code}, expected 404",
                "the public API must not publish its docs; run the current "
                "`python main.py serve` (docs_url/openapi_url disabled).",
            )


def check_openapi_host(url: str, report: Report, openapi_path: Path = OPENAPI_PATH) -> None:
    try:
        host = json.loads(openapi_path.read_text(encoding="utf-8")).get("host")
    except (OSError, ValueError):
        report.warn(
            f"could not read the host from {openapi_path.name}",
            "regenerate it with `python main.py export-openapi --host <host>`.",
        )
        return
    expected = urlsplit(url).netloc
    if host == expected:
        report.ok(f"openapi.json host matches ({expected})")
    else:
        report.warn(
            f"openapi.json host is {host!r} but the URL host is {expected!r}",
            f"run `python main.py export-openapi --host {expected}` and re-import the file "
            f"in Copilot Studio; see {MANUAL}.",
        )


def check_latency(report: Report, max_ms: float) -> None:
    if not report.latencies:
        return
    slowest = max(report.latencies, key=lambda item: item[1])
    total = sum(ms for _, ms in report.latencies)
    summary = f"{len(report.latencies)} requests, {total:.0f} ms total, slowest {slowest[1]:.0f} ms"
    if slowest[1] > max_ms:
        report.warn(
            f"latency: {summary} ({slowest[0]} over {max_ms:.0f} ms)",
            "Copilot Studio tool calls time out; try a closer tunnel region or a warm server.",
        )
    else:
        report.ok(f"latency: {summary} (limit {max_ms:.0f} ms per request)")


def load_api_key(env_name: str) -> str | None:
    value = os.environ.get(env_name)
    if not value and DEFAULT_ENV_FILE.is_file():
        value = dotenv_values(DEFAULT_ENV_FILE).get(env_name)
    return value or None


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Check the public HTTPS URL of the DeskPilot API before Copilot Studio.",
        epilog="Exit codes: 0 all passed, 1 a check failed, 2 bad usage.",
    )
    parser.add_argument("url", help="base URL, for example https://abc-8000.use.devtunnels.ms")
    parser.add_argument(
        "--api-key-env",
        default="DESKPILOT_API_KEY",
        help="name of the environment variable that holds the API key (default: %(default)s)",
    )
    parser.add_argument("--timeout", type=float, default=10.0, help="seconds per request")
    parser.add_argument(
        "--max-latency-ms", type=float, default=3000.0, help="warn above this latency"
    )
    parser.add_argument(
        "--allow-http", action="store_true", help="accept http (local tests only, warns)"
    )
    return parser


def run(args: argparse.Namespace) -> int:
    url = str(args.url).rstrip("/")
    parts = urlsplit(url)
    if not parts.netloc or parts.scheme not in {"http", "https"}:
        print(f"✗ '{url}' is not a valid URL (expected https://host[:port])")
        print("  Qué hacer: pass the base URL of the tunnel, without a path.")
        return EXIT_USAGE
    api_key = load_api_key(args.api_key_env)
    if api_key is None:
        print(f"✗ environment variable {args.api_key_env} is not set")
        print(f"  Qué hacer: set it (PowerShell: $env:{args.api_key_env} = '<key>') or use .env.")
        return EXIT_USAGE
    report = Report()
    print(f"Public URL check: {parts.scheme}://{parts.netloc}")
    if not check_scheme(url, args.allow_http, report):
        return EXIT_CHECK_FAILED
    timeout = httpx.Timeout(args.timeout)
    with httpx.Client(base_url=url, timeout=timeout, follow_redirects=False) as client:
        check_health(client, report)
        check_auth_required(client, report)
        check_search(client, api_key, report)
        check_hidden_docs(client, report)
    check_openapi_host(url, report)
    check_latency(report, args.max_latency_ms)
    verdict = "FAILED" if report.failures else "all checks passed"
    print(f"Result: {verdict} ({report.failures} failed, {report.warnings} warning(s))")
    return EXIT_CHECK_FAILED if report.failures else EXIT_OK


def main(argv: Sequence[str] | None = None) -> int:
    return run(build_parser().parse_args(argv))


if __name__ == "__main__":
    use_utf8_console()
    sys.exit(main())
