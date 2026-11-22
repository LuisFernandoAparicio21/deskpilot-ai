"""Static checks of the Dockerfile and .dockerignore (T19b, S17).

Nothing here builds an image or needs Docker or network: the files are parsed as text.
Each check guards a verified fact of docs/features/docker.md (non-root uid 10001,
HEALTHCHECK on /health, CMD ``serve --host 0.0.0.0``, no secret baked in).
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
DOCKERFILE = ROOT / "Dockerfile"
DOCKERIGNORE = ROOT / ".dockerignore"
CI_YML = ROOT / ".github" / "workflows" / "ci.yml"


def _instructions() -> list[tuple[str, str]]:
    """(INSTRUCTION, arguments) pairs: comments dropped, backslash continuations joined."""
    text = DOCKERFILE.read_text(encoding="utf-8").replace("\r\n", "\n")
    text = re.sub(r"\\\n", " ", text)
    result: list[tuple[str, str]] = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        keyword, _, rest = line.partition(" ")
        result.append((keyword.upper(), rest.strip()))
    return result


def _args(keyword: str) -> list[str]:
    return [rest for kw, rest in _instructions() if kw == keyword]


def _index(keyword: str) -> list[int]:
    return [i for i, (kw, _) in enumerate(_instructions()) if kw == keyword]


def _json_args(rest: str) -> list[str]:
    parsed = json.loads(rest)
    assert isinstance(parsed, list)
    return [str(x) for x in parsed]


def _ignore_patterns() -> list[tuple[str, bool]]:
    """(pattern, negated) from .dockerignore."""
    out: list[tuple[str, bool]] = []
    for raw in DOCKERIGNORE.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        neg = line.startswith("!")
        out.append((line[1:] if neg else line, neg))
    return out


def _to_regex(pattern: str) -> re.Pattern[str]:
    """Docker/Go filepath.Match semantics: ``*`` and ``?`` never cross ``/``; ``**`` does."""
    out = ""
    i = 0
    while i < len(pattern):
        c = pattern[i]
        if pattern.startswith("**/", i):
            out += "(?:.*/)?"
            i += 3
            continue
        if c == "*":
            out += "[^/]*"
        elif c == "?":
            out += "[^/]"
        else:
            out += re.escape(c)
        i += 1
    return re.compile(out + r"\Z")


def _matches(pattern: str, path: str) -> bool:
    """Patterns are rooted at the context root; a match on a parent directory counts."""
    rx = _to_regex(pattern.rstrip("/"))
    parts = path.split("/")
    return any(rx.match("/".join(parts[:i])) for i in range(1, len(parts) + 1))


def is_ignored(path: str) -> bool:
    """Last matching pattern wins, as in Docker."""
    ignored = False
    for pattern, neg in _ignore_patterns():
        if _matches(pattern, path):
            ignored = not neg
    return ignored


def _copy_sources() -> list[str]:
    sources: list[str] = []
    for rest in _args("COPY"):
        tokens = [t for t in rest.split() if not t.startswith("--")]
        sources.extend(tokens[:-1])
    return sources


# --- base image -------------------------------------------------------------------------


def test_from_pins_python_version_not_latest() -> None:
    froms = _args("FROM")
    assert froms, "Dockerfile has no FROM"
    for image in froms:
        ref = image.split()[0]
        name, _, tag = ref.partition(":")
        assert name == "python", ref
        assert tag
        assert tag != "latest", f"unpinned base image: {ref}"
        assert re.match(r"^\d+\.\d+(\.\d+)?(-[a-z0-9]+)?$", tag), ref


def test_from_python_matches_ci_version() -> None:
    ci = re.search(r'python-version:\s*"?(\d+\.\d+)"?', CI_YML.read_text(encoding="utf-8"))
    assert ci, "ci.yml has no python-version"
    tag = _args("FROM")[0].split()[0].partition(":")[2]
    assert tag.startswith(ci.group(1) + "-") or tag == ci.group(1), (tag, ci.group(1))


# --- user, healthcheck, command ---------------------------------------------------------


def test_non_root_user_declared_before_cmd() -> None:
    users = _args("USER")
    assert users, "no USER instruction: container would run as root"
    assert users[-1].split(":")[0] not in {"root", "0"}
    assert max(_index("USER")) < max(_index("CMD"))


def test_non_root_user_has_uid_10001() -> None:
    text = " ".join(_args("RUN"))
    assert "--uid 10001" in text
    assert "useradd" in text
    assert _args("USER")[-1] == "app"


def test_build_steps_that_write_data_run_after_user() -> None:
    """Seeding runs as app so no chown layer is needed (documented in the Dockerfile)."""
    instr = _instructions()
    seed = [i for i, (kw, r) in enumerate(instr) if kw == "RUN" and "main.py index" in r]
    assert seed
    assert seed[0] > max(_index("USER"))


def test_healthcheck_targets_health_endpoint() -> None:
    hc = _args("HEALTHCHECK")
    assert len(hc) == 1
    assert "CMD" in hc[0]
    assert "/health" in hc[0]
    assert "127.0.0.1:8000" in hc[0]
    cmd = _json_args(hc[0].split("CMD", 1)[1].strip())
    assert cmd[0] == "python"


def test_healthcheck_has_start_period_for_model_load() -> None:
    m = re.search(r"--start-period=(\d+)s", _args("HEALTHCHECK")[0])
    assert m
    assert int(m.group(1)) >= 10


def test_cmd_runs_main_serve_on_all_interfaces() -> None:
    cmds = _args("CMD")
    assert len(cmds) == 1
    argv = _json_args(cmds[0])  # exec form, so signals reach python
    assert argv[:3] == ["python", "main.py", "serve"]
    assert argv[argv.index("--host") + 1] == "0.0.0.0"


def test_no_entrypoint_overrides_serve() -> None:
    for ep in _args("ENTRYPOINT"):
        assert "serve" in ep


def test_exposes_api_port() -> None:
    assert any(p.split("/")[0] == "8000" for p in _args("EXPOSE"))


# --- secrets ----------------------------------------------------------------------------


def test_no_env_arg_copy_carries_secrets() -> None:
    secret = re.compile(r"([A-Z_]*API_KEY|[A-Z_]*SECRET|[A-Z_]*TOKEN|[A-Z_]*PASSWORD)\s*=?\s*(\S*)")
    for kw, rest in _instructions():
        if kw not in {"ENV", "ARG", "COPY", "ADD"}:
            continue
        assert not re.search(r"(^|[\s/])\.env(\.|\s|$)", rest), (kw, rest)
        for m in secret.finditer(rest):
            assert not m.group(2), f"{kw} bakes a value for {m.group(1)}"


def test_api_key_is_not_defined_anywhere_in_instructions() -> None:
    for _, rest in _instructions():
        assert "DESKPILOT_API_KEY" not in rest


def test_no_key_like_literals_in_file() -> None:
    text = DOCKERFILE.read_text(encoding="utf-8")
    assert not re.search(r"\b(sk-[A-Za-z0-9]{16,}|ghp_[A-Za-z0-9]{20,}|AKIA[0-9A-Z]{12,})", text)


# --- commands ---------------------------------------------------------------------------


def test_pip_install_uses_no_cache() -> None:
    env = " ".join(_args("ENV"))
    installs = [r for r in _args("RUN") if "pip install" in r]
    assert installs
    for rest in installs:
        assert "--no-cache-dir" in rest or "PIP_NO_CACHE_DIR=1" in env, rest


def test_no_sudo_and_no_pipe_to_shell() -> None:
    for kw, rest in _instructions():
        assert not re.search(r"\bsudo\b", rest), (kw, rest)
        assert not re.search(r"(curl|wget)\b[^|]*\|\s*(sudo\s+)?(ba|z)?sh\b", rest), (kw, rest)


def test_apt_install_is_minimal_and_cleans_lists() -> None:
    installs = [r for r in _args("RUN") if "apt-get install" in r]
    assert installs
    for rest in installs:
        assert "--no-install-recommends" in rest
        assert "rm -rf /var/lib/apt/lists/*" in rest


def test_model_and_data_prepared_at_build_time() -> None:
    joined = " ".join(r for r in _args("RUN") if "main.py" in r)
    for step in ("generate-data", "load-db", "index"):
        assert f"main.py {step}" in joined
    assert joined.index("generate-data") < joined.index("load-db") < joined.index("main.py index")
    instr = _instructions()
    offline = next(i for i, (k, r) in enumerate(instr) if k == "ENV" and "HF_HUB_OFFLINE=1" in r)
    index_run = next(i for i, (k, r) in enumerate(instr) if k == "RUN" and "main.py index" in r)
    assert offline > index_run, "offline flag would block the model download at build"


# --- .dockerignore vs COPY --------------------------------------------------------------


@pytest.mark.parametrize(
    "path",
    [
        ".env",
        ".env.local",
        ".venv/lib/x.py",
        "scratch/a.txt",
        ".git/HEAD",
        "logs/app.log",
        "data/vectordb/chroma.sqlite3",
        "data/vectordb/models/m.onnx",
    ],
)
def test_dockerignore_excludes(path: str) -> None:
    assert is_ignored(path), f"{path} would enter the build context"


def test_dockerignore_keeps_env_example() -> None:
    assert not is_ignored(".env.example")


@pytest.mark.parametrize(
    "path",
    [
        "data/knowledge_base/doc.txt",
        "config.yaml",
        "src/api/app.py",
        "main.py",
        "requirements.txt",
        "integrations/fabric/sql/01_top_incidencias.sql",
    ],
)
def test_dockerignore_does_not_exclude_runtime_files(path: str) -> None:
    assert not is_ignored(path), f"{path} is needed by the image but ignored"


def test_every_copy_source_exists_and_is_not_ignored() -> None:
    sources = [s.removeprefix("./") for s in _copy_sources()]
    required = {"requirements.txt", "config.yaml", "main.py", "src", "data/knowledge_base"}
    assert required <= set(sources)
    for rel in sources:
        target = ROOT / rel
        assert target.exists(), f"COPY source missing: {rel}"
        assert not is_ignored(rel), f"COPY source ignored by .dockerignore: {rel}"
        if target.is_dir():
            files = [p for p in target.rglob("*") if p.is_file() and "__pycache__" not in p.parts]
            assert files, f"COPY dir is empty: {rel}"
            kept = [p for p in files if not is_ignored(p.relative_to(ROOT).as_posix())]
            assert kept, f"every file under {rel} is ignored"


def test_knowledge_base_files_survive_the_ignore_rules() -> None:
    """The ``*.md`` rule is root-level only in Docker, so it must not strip the knowledge base."""
    kb = ROOT / "data" / "knowledge_base"
    files = [p for p in kb.rglob("*") if p.is_file()]
    assert files
    dropped = [p.name for p in files if is_ignored(p.relative_to(ROOT).as_posix())]
    assert not dropped, f"knowledge base files dropped from the build context: {dropped[:5]}"


def test_is_ignored_helper_detects_nesting_and_globs() -> None:
    """Guards the helper itself so the assertions above cannot pass vacuously."""
    assert is_ignored("a/b/__pycache__/x.pyc")
    assert is_ignored("README.md")
    assert not is_ignored("data/knowledge_base/KB-001.md"), "*.md is root-level only in Docker"
    assert not is_ignored("src/main_module.py")
