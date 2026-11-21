"""Versioned index directories and the atomic ``CURRENT`` pointer (RF-15, HU-08).

Layout of ``paths.vectordb``::

    data/vectordb/
        20261121T183000123456Z/   one complete Chroma index per ``main.py index`` run
        20261122T090000000000Z/
        CURRENT                   name of the version the API must read

Why: Chroma documents ``PersistentClient`` for local use and recommends a server for
production; it does not support several processes sharing one path (the Chroma
Cookbook says "Chroma is not process-safe for concurrent writers sharing the same local
persistence path"). So no process ever writes into the directory another one reads:
``index`` builds a new directory, validates it, swaps ``CURRENT`` with ``os.replace``
(documented as atomic on POSIX; readers ignore a missing or invalid pointer) and prunes
old versions. The API keeps serving the old
version until ``CurrentStore`` notices the new pointer and reopens, without a restart.
"""

from __future__ import annotations

import datetime as dt
import logging
import os
import re
import shutil
import threading
import time
from pathlib import Path

from src.utils.config import Settings
from src.vectordb.base import VectorStore
from src.vectordb.chroma_store import ChromaVectorStore, IndexNotFoundError

logger = logging.getLogger(__name__)

POINTER_NAME = "CURRENT"
KEEP_VERSIONS = 2
_VERSION = re.compile(r"^\d{8}T\d{12}Z$")
_TRASH_SUFFIX = ".trash"
_REPLACE_ATTEMPTS = 10
_REPLACE_DELAY_S = 0.05


def new_version_name(now: dt.datetime | None = None) -> str:
    """UTC timestamp with microseconds, e.g. ``20261121T183000123456Z`` (sorts by time)."""
    moment = (now or dt.datetime.now(dt.UTC)).astimezone(dt.UTC)
    return moment.strftime("%Y%m%dT%H%M%S%fZ")


def is_version_name(name: str) -> bool:
    return bool(_VERSION.fullmatch(name))


def list_versions(root: Path) -> list[str]:
    """Version directories under ``root``, oldest first (other entries are ignored)."""
    if not root.is_dir():
        return []
    return sorted(p.name for p in root.iterdir() if p.is_dir() and is_version_name(p.name))


def read_current(root: Path) -> str | None:
    """Version named by ``CURRENT``, or None when it is missing, invalid or dangling."""
    try:
        name = (root / POINTER_NAME).read_text(encoding="utf-8").strip()
    except OSError:
        return None
    if not is_version_name(name) or not (root / name).is_dir():
        return None
    return name


def write_current(root: Path, version: str) -> None:
    """Point ``CURRENT`` at ``version`` atomically: temp file + fsync + ``os.replace``.

    On Windows ``os.replace`` fails while a reader has the pointer open for a moment,
    so it retries briefly before giving up.
    """
    if not is_version_name(version) or not (root / version).is_dir():
        raise ValueError(f"unknown index version: {version!r}")
    tmp = root / f"{POINTER_NAME}.{os.getpid()}.tmp"
    with tmp.open("w", encoding="utf-8") as handle:
        handle.write(version + "\n")
        handle.flush()
        os.fsync(handle.fileno())
    for attempt in range(1, _REPLACE_ATTEMPTS + 1):
        try:
            os.replace(tmp, root / POINTER_NAME)
            return
        except PermissionError:
            if attempt == _REPLACE_ATTEMPTS:
                tmp.unlink(missing_ok=True)
                raise
            time.sleep(_REPLACE_DELAY_S)


def prune_versions(root: Path, keep: int = KEEP_VERSIONS) -> list[str]:
    """Delete all but the ``keep`` newest versions (never the current one).

    Each old directory is first renamed: on Windows that fails while another process
    still has the index open, so a version in use is skipped instead of half-deleted
    (it is retried on the next run). Returns the versions actually removed.
    """
    if keep < 1:
        raise ValueError(f"keep must be at least 1, got {keep}")
    for leftover in root.glob(f"*{_TRASH_SUFFIX}"):
        shutil.rmtree(leftover, ignore_errors=True)
    current = read_current(root)
    versions = list_versions(root)
    removed: list[str] = []
    for name in versions[:-keep]:
        if name == current:
            continue
        trash = root / f"{name}{_TRASH_SUFFIX}"
        try:
            os.rename(root / name, trash)
        except OSError as exc:
            logger.warning(
                "Old index version in use; it will be pruned on the next run",
                extra={"version": name, "error": type(exc).__name__},
            )
            continue
        shutil.rmtree(trash, ignore_errors=True)
        removed.append(name)
    return removed


class IndexPointerWatcher:
    """Detects ``CURRENT`` changes cheaply: ``stat`` first, content only when it changed."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self.version: str | None = None
        self._signature: tuple[int, int, int] | None = None

    def _stat(self) -> tuple[int, int, int] | None:
        try:
            st = (self.root / POINTER_NAME).stat()
        except OSError:
            return None
        return (st.st_ino, st.st_mtime_ns, st.st_size)

    def forget(self, version: str | None) -> None:
        """Go back to ``version`` so the next ``check`` re-reads the pointer."""
        self.version = version
        self._signature = None

    def check(self) -> str | None:
        """The new version if ``CURRENT`` now names a different one, otherwise None."""
        signature = self._stat()
        if signature is not None and signature == self._signature:
            return None
        self._signature = signature
        version = read_current(self.root)
        if version is None or version == self.version:
            return None
        self.version = version
        return version


class CurrentStore:
    """Thread-safe handle to the index named by ``CURRENT``, reopened when it changes.

    The API (T16) calls ``get()`` per request. The previous store is closed one swap
    later, so queries already running on it can finish.
    """

    def __init__(self, root: Path, collection: str) -> None:
        self._root = root
        self._collection = collection
        self._watcher = IndexPointerWatcher(root)
        self._lock = threading.Lock()
        self._store: ChromaVectorStore | None = None
        self._retired: ChromaVectorStore | None = None

    @property
    def version(self) -> str | None:
        return self._watcher.version

    def get(self) -> VectorStore:
        with self._lock:
            previous = self._watcher.version
            new_version = self._watcher.check()
            if new_version is not None:
                try:
                    store = ChromaVectorStore(
                        self._root / new_version, self._collection, create=False
                    )
                except IndexNotFoundError:
                    self._watcher.forget(previous)  # retry on the next call
                    if self._store is None:
                        raise
                    logger.exception("New index version unusable; keeping the previous one")
                    return self._store
                if self._retired is not None:
                    self._retired.close()
                self._retired, self._store = self._store, store
                logger.info("Vector index opened", extra={"version": new_version})
            if self._store is None:
                raise IndexNotFoundError(
                    f"no index in {self._root} (missing {POINTER_NAME}); run: python main.py index"
                )
            return self._store

    def close(self) -> None:
        with self._lock:
            for store in (self._retired, self._store):
                if store is not None:
                    store.close()
            self._store = self._retired = None

    @classmethod
    def from_settings(cls, settings: Settings) -> CurrentStore:
        return cls(settings.paths.vectordb, settings.vectordb.collection)


def open_current_store(settings: Settings) -> ChromaVectorStore:
    """Open (read-only use) the version named by ``CURRENT``; the caller must ``close()`` it.

    Long-running processes such as the API should use ``CurrentStore.from_settings``,
    which also reopens the index when ``main.py index`` publishes a new version.
    """
    root = settings.paths.vectordb
    version = read_current(root)
    if version is None:
        raise IndexNotFoundError(
            f"no index in {root} (missing {POINTER_NAME}); run: python main.py index"
        )
    return ChromaVectorStore(root / version, settings.vectordb.collection, create=False)
