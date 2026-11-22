"""README visual refresh audit: banner, <picture>, badges, figures and result block.

Structure only, no network. Docs are never edited here: a mismatch fails with
"doc vs real". Live badge reachability is checked by hand (curl -I), not in tests.
"""

from __future__ import annotations

import colorsys
import io
import json
import re
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from urllib.parse import parse_qsl, unquote, urlsplit

import pytest

from src.utils.config import PROJECT_ROOT

README = PROJECT_ROOT / "README.md"
PROCEDURE = PROJECT_ROOT / "docs" / "testing-procedure.md"
SUMMARY = PROJECT_ROOT / "tests" / "eval" / "results.summary.json"
NOTE = "Synthetic data generated for this project; figures are illustrative"
# README v2 (docs/features/readme-redesign.md, research criterion 19): the typing-svg and the
# stack badges were removed, so only shields.io may serve remote images.
ALLOWED_HOSTS = {"img.shields.io"}
# Remote images in README v2: CI, release, license, coverage + Copilot Studio and Fabric.
EXPECTED_REMOTE_BADGES = 6
# Of those, the /badge/ (static) ones: coverage + the two generated Microsoft platform badges.
EXPECTED_STATIC_BADGES = 3
NOTE_ES = "Datos sintéticos generados para este proyecto; las cifras son ilustrativas."
H2_PREFIX = r"^##\s+(?:\W+\s+)?"

IMG_SRC_RE = re.compile(r"<img\b[^>]*?\bsrc=\"([^\"]+)\"", re.I)
MD_IMG_RE = re.compile(r"!\[[^\]]*\]\(([^)\s]+)")
SRCSET_RE = re.compile(r"<source\b[^>]*?\bsrcset=\"([^\"]+)\"", re.I)
REMOTE_PREFIXES = ("http:", "https:", "//")


def _text() -> str:
    return README.read_text(encoding="utf-8")


def _image_refs(text: str) -> list[str]:
    return IMG_SRC_RE.findall(text) + MD_IMG_RE.findall(text) + SRCSET_RE.findall(text)


def _local_images() -> list[str]:
    return sorted({r for r in _image_refs(_text()) if not r.startswith(REMOTE_PREFIXES)})


def _remote_images() -> list[str]:
    return [r for r in _image_refs(_text()) if r.startswith(REMOTE_PREFIXES)]


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


# (1) local images ----------------------------------------------------------------------


def test_expected_banners_are_referenced() -> None:
    local = _local_images()
    assert "docs/assets/banner-dark.svg" in local
    assert "docs/assets/banner-light.svg" in local


@pytest.mark.parametrize("ref", _local_images())
def test_local_image_exists_and_is_safe_svg(ref: str) -> None:
    path = PROJECT_ROOT / ref
    assert path.is_file(), f"README references {ref}, real: file missing"
    if path.suffix.lower() != ".svg":
        return
    raw_text = path.read_text(encoding="utf-8")
    root = ET.fromstring(raw_text)  # ParseError means malformed XML
    assert _local_name(root.tag) == "svg"
    assert root.get("viewBox"), f"{ref}: viewBox missing"
    has_title = any(_local_name(e.tag) == "title" and (e.text or "").strip() for e in root.iter())
    assert has_title or (root.get("aria-label") or "").strip(), f"{ref}: no <title>/aria-label"
    names = {_local_name(e.tag).lower() for e in root.iter()}
    assert not names & {"script", "foreignobject", "image", "iframe"}, f"{ref}: {names}"
    raw = raw_text.lower()
    assert not re.search(r"(?:href|src)\s*=\s*[\"'](?:https?:)?//", raw), f"{ref}: external ref"
    assert not re.search(r"url\(\s*[\"']?(?:https?:)?//", raw), f"{ref}: external url()"
    assert "@import" not in raw, f"{ref}: @import"
    assert not re.search(r"\bon[a-z]+\s*=", raw), f"{ref}: event handler"


# (2) <picture> -------------------------------------------------------------------------


def test_picture_has_dark_and_light_sources_and_alt() -> None:
    match = re.search(r"<picture>(.*?)</picture>", _text(), re.S)
    assert match, "README has no <picture>"
    block = match.group(1)
    media: dict[str, str] = {}
    for source in re.findall(r"<source\b[^>]*>", block):
        scheme = re.search(r"media=\"\(prefers-color-scheme:\s*(dark|light)\)\"", source)
        if scheme:
            media[scheme.group(1)] = source
    assert set(media) == {"dark", "light"}, f"sources by scheme: {sorted(media)}"
    assert "banner-dark.svg" in media["dark"] and "banner-light.svg" in media["light"]
    img = re.search(r"<img\b[^>]*>", block)
    assert img, "<picture> has no <img>"
    alt = re.search(r"\balt=\"([^\"]*)\"", img.group(0))
    assert alt and alt.group(1).strip(), "<img> alt missing or empty"


# (3) badges ----------------------------------------------------------------------------


def test_all_remote_images_are_https_from_allowed_hosts() -> None:
    remote = _remote_images()
    # Exact, not a floor: the redesign cut 13 badges + typing-svg to 6 meaningful ones
    # (docs/research/readme-for-recruiters.md criterion 19; Wei: badges only if meaningful).
    # A new decorative badge must be a conscious change here, not a silent addition.
    assert len(remote) == EXPECTED_REMOTE_BADGES, f"expected 6 badges, found {len(remote)}"
    for url in remote:
        parts = urlsplit(url)
        assert parts.scheme == "https", f"not https: {url}"
        assert parts.hostname in ALLOWED_HOSTS, f"host outside allowlist: {url}"
    plain = re.findall(r"(?:href|src|srcset)=\"(http://[^\"]+)|\]\((http://[^)\s]+)", _text())
    assert not plain, f"plain http link in README: {plain}"


def test_badge_query_parameters_are_well_formed() -> None:
    for url in _remote_images():
        parts = urlsplit(url)
        assert not parts.fragment, url
        if not parts.query:
            continue
        pairs = parse_qsl(parts.query, keep_blank_values=True, separator="&")
        assert len(pairs) == len(parts.query.split("&")), f"malformed query: {url}"
        for key, value in pairs:
            assert re.fullmatch(r"[A-Za-z]+", key), f"bad key {key!r}: {url}"
            assert value != "", f"empty value for {key}: {url}"
            if key in {"width", "height"}:
                assert value.isdigit(), f"{key} not numeric: {url}"
            if key in {"color", "labelColor", "logoColor"} and re.fullmatch(r"[0-9A-Fa-f]+", value):
                assert len(value) in {3, 6}, f"bad hex {value}: {url}"


def _badge_fields(url: str) -> list[str]:
    segment = unquote(urlsplit(url).path.split("/badge/", 1)[1])
    # shields: "--" is a literal dash, "-" separates label, message and color.
    return [f.replace("\0", "-") for f in segment.replace("--", "\0").split("-")]


def test_static_shields_badges_have_label_message_color() -> None:
    static = [u for u in _remote_images() if "/badge/" in u]
    assert len(static) == EXPECTED_STATIC_BADGES, f"static badges: {len(static)}"
    for url in static:
        fields = _badge_fields(url)
        assert len(fields) == 3 and all(f.strip() for f in fields), f"label-message-color: {url}"


def _is_greenish(color: str) -> bool:
    if color.lower() in {"green", "brightgreen", "success", "yellowgreen", "4c1", "97ca00"}:
        return True
    if re.fullmatch(r"[0-9A-Fa-f]{6}", color):
        r, g, b = (int(color[i : i + 2], 16) / 255 for i in (0, 2, 4))
        hue, sat, _ = colorsys.rgb_to_hsv(r, g, b)
        return sat > 0.25 and 0.2 <= hue <= 0.5
    return False


def test_greenish_detector_is_not_vacuous() -> None:
    assert _is_greenish("brightgreen") and _is_greenish("2EA043")
    assert not _is_greenish("6B7280") and not _is_greenish("E53535")


@pytest.mark.parametrize("platform", ["Fabric", "Copilot Studio"])
def test_unvalidated_platform_badges_say_pending_and_are_not_green(platform: str) -> None:
    badges = [
        u
        for u in _remote_images()
        if "/badge/" in u and platform.lower() in unquote(u).split("/badge/")[1].lower()
    ]
    assert len(badges) == 1, f"{platform}: expected 1 badge, real {len(badges)}"
    label, message, color = _badge_fields(badges[0])
    assert platform.lower() in label.lower()
    assert "pending" in message.lower(), f"{platform} badge must say pending: {message}"
    assert "validated" not in message.lower().replace("pending validation", ""), (
        f"{platform} badge claims validated: {message}"
    )
    assert not _is_greenish(color.split("?")[0]), f"{platform} badge is green: {color}"
    alt = re.search(r"!\[([^\]]*)\]\(" + re.escape(badges[0]), _text())
    assert alt, f"{platform} badge has no markdown alt"
    alt_text = alt.group(1).lower()
    assert "pending" in alt_text and "validated" not in alt_text.replace("pending validation", "")


# (4) coverage badge --------------------------------------------------------------------


def _badge_coverage() -> float:
    m = re.search(r"badge/coverage-(\d+(?:\.\d+)?)%25", _text())
    assert m, "coverage badge not found"
    return float(m.group(1))


def test_coverage_badge_matches_last_declared_measurement() -> None:
    procedure = PROCEDURE.read_text(encoding="utf-8")
    declared = re.search(r"Calidad de código[^\n]*?\|\s*(\d+(?:\.\d+)?)%,", procedure)
    assert declared, "docs/testing-procedure.md declares no coverage figure"
    assert _badge_coverage() == float(declared.group(1)), "badge vs testing-procedure"
    row = re.search(r"`src/` coverage\s*\|\s*(\d+(?:\.\d+)?)%", _text())
    assert row and float(row.group(1)) == _badge_coverage(), "badge vs README table"


def test_coverage_badge_matches_local_coverage_data_when_complete() -> None:
    data = PROJECT_ROOT / ".coverage"
    if not data.exists():
        pytest.skip("no .coverage data file")
    coverage = pytest.importorskip("coverage")
    cov = coverage.Coverage(data_file=str(data))
    cov.load()
    measured = {Path(f).resolve() for f in cov.get_data().measured_files()}
    expected = {p.resolve() for p in (PROJECT_ROOT / "src").rglob("*.py") if p.stat().st_size}
    if not expected <= measured:
        pytest.skip(".coverage comes from a partial run")
    total = cov.report(file=io.StringIO(), include=[str(PROJECT_ROOT / "src" / "*")])
    assert abs(total - _badge_coverage()) < 0.01, f"badge vs real coverage {total:.2f}"


# (5) figures ---------------------------------------------------------------------------


def test_results_table_matches_eval_summary() -> None:
    s = json.loads(SUMMARY.read_text(encoding="utf-8"))
    m = s["metrics"]
    after = _text().split("<!-- RESULTS:END -->", 1)[1].splitlines()
    row = next(r for r in after if r.startswith("| Evaluation cases"))
    assert f"**{s['passed']} of {s['total']}** ({m['aprobados']['pct']}%)" in row
    for key, label in (("retrieval_top3", "top-3"), ("rechazo", "refusal")):
        assert f"{label} {m[key]['passed']}/{m[key]['total']}" in row, f"{label}: {row}"
    lat = next(r for r in after if r.startswith("| Latency per case"))
    assert f"p50 {s['latency_ms']['p50']} ms, p95 {s['latency_ms']['p95']} ms" in lat


def _pytest_totals(text: str, verb: str) -> tuple[int, int, int]:
    m = re.search(rf"(\d+) {verb}, (\d+) skipped, (\d+) deselected", text)
    assert m, f"no 'N {verb}, N skipped, N deselected' line"
    return int(m.group(1)), int(m.group(2)), int(m.group(3))


def test_pytest_totals_match_testing_procedure() -> None:
    """README row says '<N> run' (all passing); the procedure says '<N> passed'."""
    readme = _text()
    declared = _pytest_totals(PROCEDURE.read_text(encoding="utf-8"), "passed")
    row = next(r for r in readme.splitlines() if r.startswith("| Tests (default run"))
    assert _pytest_totals(row, "run") == declared, f"README {row!r} vs procedure {declared}"


# (6) English summary and synthetic note ------------------------------------------------


def test_intro_paragraph_comes_before_why_section_without_language_label() -> None:
    """README v2 has no '**English:**' block: the whole file is English, so the intro
    paragraph right after the H1 is the summary and must precede the 'Why' section."""
    lines = _text().splitlines()
    h1 = next(i for i, ln in enumerate(lines) if ln.startswith("# "))
    why = next(i for i, ln in enumerate(lines) if re.match(H2_PREFIX + r"Why this project", ln))
    intro = next(i for i in range(h1 + 1, len(lines)) if lines[i].strip())
    assert intro < why, "intro must come before 'Why this project'"
    assert lines[intro].startswith("DeskPilot AI is"), lines[intro]
    assert "**English:**" not in _text(), "language label must be gone"


def test_synthetic_data_note_is_in_first_25_lines() -> None:
    head = "\n".join(_text().splitlines()[:25])
    assert f"**{NOTE}.**" in head
    assert f"<sub>{NOTE_ES}</sub>" in head


# (7) RESULTS block ---------------------------------------------------------------------


def test_results_block_is_up_to_date() -> None:
    proc = subprocess.run(
        [sys.executable, "-m", "scripts.update_readme_results", "--check"],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )
    assert proc.returncode == 0, f"--check exit {proc.returncode}: {proc.stdout}{proc.stderr}"
    assert "<!-- RESULTS:START -->" in _text() and "<!-- RESULTS:END -->" in _text()


def test_testing_procedure_latency_matches_eval_summary() -> None:
    lat = json.loads(SUMMARY.read_text(encoding="utf-8"))["latency_ms"]
    procedure = PROCEDURE.read_text(encoding="utf-8")
    assert f"p50 {lat['p50']} ms, p95 {lat['p95']} ms" in procedure, "testing-procedure latency"
