"""Unit tests for src/vectordb: Chroma and in-memory stores, CURRENT pointer, pruning."""

from __future__ import annotations

import datetime as dt
import os
from collections.abc import Callable, Iterator
from pathlib import Path

import pytest

from src.chunking.section_chunker import Chunk, ChunkMetadata
from src.embeddings import FakeEmbedder
from src.utils.config import load_settings
from src.vectordb import (
    ChromaVectorStore,
    CurrentStore,
    IndexNotFoundError,
    IndexPointerWatcher,
    InMemoryVectorStore,
    ScoredChunk,
    VectorStore,
    distance_to_similarity,
    list_versions,
    new_version_name,
    open_current_store,
    prune_versions,
    read_current,
    write_current,
)

COLLECTION = "deskpilot_kb"
EMBEDDER = FakeEmbedder()


def _chunk(article_id: str, seccion: str, categoria: str, text: str) -> Chunk:
    metadata = ChunkMetadata(
        article_id=article_id,
        titulo=f"Título {article_id}",
        categoria=categoria,
        subcategoria="",
        idioma="es",
        seccion=seccion,
        palabras_clave="",
        source=f"data/knowledge_base/{article_id}.md",
    )
    return Chunk(chunk_id=f"{article_id}#{seccion}#0", text=text, metadata=metadata)


CHUNKS = [
    _chunk("KB-002", "sintoma", "Accesos", "Usuario de Windows bloqueado tras intentos fallidos"),
    _chunk("KB-004", "sintoma", "Red", "La VPN no conecta desde casa"),
    _chunk("KB-005", "sintoma", "Hardware", "La impresora no imprime documentos"),
    _chunk("KB-099", "sintoma", "Red", "Usuario sin red ni VPN en sucursal"),
]


def _vectors(chunks: list[Chunk]) -> list[list[float]]:
    return EMBEDDER.embed_documents([c.text for c in chunks])


StoreFactory = Callable[[], VectorStore]


@pytest.fixture(params=["chroma", "memory"])
def make_store(request: pytest.FixtureRequest, tmp_path: Path) -> Iterator[StoreFactory]:
    opened: list[ChromaVectorStore] = []

    def _make() -> VectorStore:
        if request.param == "memory":
            return InMemoryVectorStore()
        store = ChromaVectorStore(tmp_path / "chroma", COLLECTION)
        opened.append(store)
        return store

    yield _make
    for store in opened:
        store.close()


# --- Store contract (Chroma and in-memory) ---------------------------------------------


def test_upsert_then_count_and_upsert_again_is_idempotent(make_store: StoreFactory) -> None:
    store = make_store()
    assert store.count() == 0
    store.upsert(CHUNKS, _vectors(CHUNKS))
    store.upsert(CHUNKS, _vectors(CHUNKS))
    assert store.count() == len(CHUNKS)


def test_query_returns_the_most_similar_chunk_first(make_store: StoreFactory) -> None:
    store = make_store()
    store.upsert(CHUNKS, _vectors(CHUNKS))
    results = store.query(EMBEDDER.embed_query("mi usuario de Windows está bloqueado"), top_k=2)
    assert len(results) == 2
    assert all(isinstance(r, ScoredChunk) for r in results)
    assert results[0].chunk == CHUNKS[0]
    assert results[0].similarity >= results[1].similarity


def test_similarity_is_between_0_and_1(make_store: StoreFactory) -> None:
    store = make_store()
    store.upsert(CHUNKS, _vectors(CHUNKS))
    results = store.query(EMBEDDER.embed_query("usuario bloqueado VPN"), top_k=len(CHUNKS))
    assert len(results) == len(CHUNKS)
    assert all(0.0 <= r.similarity <= 1.0 for r in results)
    exact = store.query(_vectors(CHUNKS[:1])[0], top_k=1)[0]
    assert exact.similarity == pytest.approx(1.0, abs=1e-5)


def test_query_filters_by_category(make_store: StoreFactory) -> None:
    store = make_store()
    store.upsert(CHUNKS, _vectors(CHUNKS))
    query = EMBEDDER.embed_query("usuario bloqueado")
    results = store.query(query, top_k=5, where={"categoria": "Red"})
    assert {r.chunk.metadata.article_id for r in results} == {"KB-004", "KB-099"}
    both = store.query(query, top_k=5, where={"categoria": "Red", "article_id": "KB-004"})
    assert [r.chunk.chunk_id for r in both] == ["KB-004#sintoma#0"]
    assert store.query(query, top_k=5, where={"categoria": "Nada"}) == []


def test_query_on_an_empty_store_returns_nothing(make_store: StoreFactory) -> None:
    assert make_store().query(EMBEDDER.embed_query("vpn"), top_k=3) == []


def test_upsert_rejects_mismatched_lengths(make_store: StoreFactory) -> None:
    with pytest.raises(ValueError, match="embeddings"):
        make_store().upsert(CHUNKS, _vectors(CHUNKS[:1]))


def test_upsert_of_nothing_is_a_no_op(make_store: StoreFactory) -> None:
    store = make_store()
    store.upsert([], [])
    assert store.count() == 0


def test_top_k_must_be_positive(make_store: StoreFactory) -> None:
    with pytest.raises(ValueError, match="top_k"):
        make_store().query(EMBEDDER.embed_query("vpn"), top_k=0)


def test_stores_satisfy_the_protocol(make_store: StoreFactory) -> None:
    assert isinstance(make_store(), VectorStore)


@pytest.mark.parametrize(
    ("distance", "similarity"),
    [(0.0, 1.0), (0.25, 0.75), (1.0, 0.0), (1.7, 0.0), (-1e-7, 1.0), (float("nan"), 0.0)],
)
def test_distance_to_similarity_clamps_cosine_similarity(
    distance: float, similarity: float
) -> None:
    assert distance_to_similarity(distance) == pytest.approx(similarity)


# --- Chroma specifics ------------------------------------------------------------------


def test_chroma_persists_and_reopens_with_cosine_space(tmp_path: Path) -> None:
    path = tmp_path / "chroma"
    store = ChromaVectorStore(path, COLLECTION, metadata={"embedding_model": "fake"})
    store.upsert(CHUNKS, _vectors(CHUNKS))
    store.close()
    reopened = ChromaVectorStore(path, COLLECTION, create=False)
    try:
        assert reopened.count() == len(CHUNKS)
        assert reopened.space == "cosine"
        assert reopened.metadata["embedding_model"] == "fake"
    finally:
        reopened.close()


def test_chroma_open_missing_collection_raises_index_not_found(tmp_path: Path) -> None:
    with pytest.raises(IndexNotFoundError):
        ChromaVectorStore(tmp_path / "empty", COLLECTION, create=False)


# --- Versions and the CURRENT pointer --------------------------------------------------


def test_version_names_sort_chronologically() -> None:
    early = new_version_name(dt.datetime(2026, 11, 21, 9, 5, 1, 7, tzinfo=dt.UTC))
    late = new_version_name(dt.datetime(2026, 11, 21, 10, 0, 0, 0, tzinfo=dt.UTC))
    assert early == "20261121T090501000007Z"
    assert sorted([late, early]) == [early, late]


def _make_versions(root: Path, n: int) -> list[str]:
    names = [f"2026112{i}T000000000000Z" for i in range(n)]
    for name in names:
        (root / name).mkdir(parents=True)
    return names


def test_list_versions_ignores_other_entries(tmp_path: Path) -> None:
    names = _make_versions(tmp_path, 3)
    (tmp_path / "models").mkdir()
    (tmp_path / ".gitkeep").touch()
    write_current(tmp_path, names[0])
    assert list_versions(tmp_path) == names
    assert list_versions(tmp_path / "missing") == []


def test_write_current_is_atomic_and_leaves_no_temp_files(tmp_path: Path) -> None:
    names = _make_versions(tmp_path, 2)
    write_current(tmp_path, names[0])
    write_current(tmp_path, names[1])
    assert read_current(tmp_path) == names[1]
    assert sorted(p.name for p in tmp_path.iterdir() if p.is_file()) == ["CURRENT"]


def test_write_current_rejects_unknown_versions(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="version"):
        write_current(tmp_path, "20261121T000000000000Z")
    with pytest.raises(ValueError, match="version"):
        write_current(tmp_path, "../etc")


def test_write_current_retries_while_windows_locks_the_pointer(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    names = _make_versions(tmp_path, 1)
    real_replace = os.replace
    calls: list[int] = []

    def flaky_replace(src: str, dst: str) -> None:
        calls.append(1)
        if len(calls) < 3:
            raise PermissionError("file in use")
        real_replace(src, dst)

    monkeypatch.setattr("src.vectordb.versions.os.replace", flaky_replace)
    monkeypatch.setattr("src.vectordb.versions.time.sleep", lambda _s: None)
    write_current(tmp_path, names[0])
    assert len(calls) == 3
    assert read_current(tmp_path) == names[0]


def test_read_current_handles_missing_or_invalid_pointers(tmp_path: Path) -> None:
    assert read_current(tmp_path) is None
    (tmp_path / "CURRENT").write_text("../outside\n", encoding="utf-8")
    assert read_current(tmp_path) is None
    (tmp_path / "CURRENT").write_text("20261121T000000000000Z\n", encoding="utf-8")
    assert read_current(tmp_path) is None  # the directory does not exist


def test_prune_keeps_the_two_most_recent_and_the_current(tmp_path: Path) -> None:
    names = _make_versions(tmp_path, 5)
    write_current(tmp_path, names[0])  # an old version still in use is never deleted
    removed = prune_versions(tmp_path, keep=2)
    assert removed == names[1:3]
    assert list_versions(tmp_path) == [names[0], *names[3:]]
    assert not [p for p in tmp_path.iterdir() if "trash" in p.name]


def test_prune_skips_versions_it_cannot_move(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    names = _make_versions(tmp_path, 3)
    write_current(tmp_path, names[2])

    def locked(src: Path, dst: Path) -> None:
        raise PermissionError("another process has the index open")

    monkeypatch.setattr("src.vectordb.versions.os.rename", locked)
    assert prune_versions(tmp_path, keep=2) == []
    assert list_versions(tmp_path) == names


def test_prune_rejects_keep_below_one(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="keep"):
        prune_versions(tmp_path, keep=0)


# --- Pointer watcher and CurrentStore ---------------------------------------------------


def _build_version(root: Path, name: str, chunks: list[Chunk]) -> None:
    store = ChromaVectorStore(root / name, COLLECTION)
    store.upsert(chunks, _vectors(chunks))
    store.close()
    write_current(root, name)


def test_watcher_reports_a_new_version_once(tmp_path: Path) -> None:
    names = _make_versions(tmp_path, 2)
    watcher = IndexPointerWatcher(tmp_path)
    assert watcher.check() is None
    write_current(tmp_path, names[0])
    assert watcher.check() == names[0]
    assert watcher.check() is None
    write_current(tmp_path, names[1])
    assert watcher.check() == names[1]
    assert watcher.version == names[1]


def test_current_store_reopens_when_the_pointer_changes(tmp_path: Path) -> None:
    first, second = "20261121T000000000000Z", "20261122T000000000000Z"
    current = CurrentStore(tmp_path, COLLECTION)
    with pytest.raises(IndexNotFoundError, match="main.py index"):
        current.get()
    _build_version(tmp_path, first, CHUNKS[:2])
    try:
        assert current.get().count() == 2
        assert current.version == first
        _build_version(tmp_path, second, CHUNKS)
        assert current.get().count() == len(CHUNKS)
        assert current.version == second
    finally:
        current.close()


def test_current_store_keeps_serving_when_the_new_version_is_unusable(tmp_path: Path) -> None:
    good, broken = "20261121T000000000000Z", "20261122T000000000000Z"
    _build_version(tmp_path, good, CHUNKS)
    current = CurrentStore(tmp_path, COLLECTION)
    try:
        assert current.get().count() == len(CHUNKS)
        (tmp_path / broken).mkdir()  # a directory without the collection
        write_current(tmp_path, broken)
        assert current.get().count() == len(CHUNKS)
        assert current.version == good
    finally:
        current.close()


def test_open_current_store_uses_paths_and_collection_from_settings(tmp_path: Path) -> None:
    settings = load_settings(env_file=tmp_path / "missing.env")
    paths = settings.paths.model_copy(update={"vectordb": tmp_path / "vectordb"})
    settings = settings.model_copy(update={"paths": paths})
    with pytest.raises(IndexNotFoundError, match="main.py index"):
        open_current_store(settings)
    _build_version(paths.vectordb, "20261121T000000000000Z", CHUNKS)
    store = open_current_store(settings)
    try:
        assert store.count() == len(CHUNKS)
    finally:
        store.close()
    current = CurrentStore.from_settings(settings)
    try:
        assert current.get().count() == len(CHUNKS)
    finally:
        current.close()


def test_upsert_rejects_vectors_of_different_sizes(make_store: StoreFactory) -> None:
    with pytest.raises(ValueError, match="dimension"):
        make_store().upsert(CHUNKS[:2], [[1.0, 0.0], [1.0]])


def test_write_current_gives_up_after_repeated_lock_errors(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    names = _make_versions(tmp_path, 1)

    def locked(src: str, dst: str) -> None:
        raise PermissionError("file in use")

    monkeypatch.setattr("src.vectordb.versions.os.replace", locked)
    monkeypatch.setattr("src.vectordb.versions.time.sleep", lambda _s: None)
    with pytest.raises(PermissionError):
        write_current(tmp_path, names[0])
    assert list(tmp_path.glob("CURRENT*")) == []


def test_prune_removes_leftover_trash_directories(tmp_path: Path) -> None:
    names = _make_versions(tmp_path, 1)
    write_current(tmp_path, names[0])
    (tmp_path / "20261120T000000000000Z.trash" / "sub").mkdir(parents=True)
    assert prune_versions(tmp_path) == []
    assert sorted(p.name for p in tmp_path.iterdir()) == sorted(["CURRENT", names[0]])


def test_current_store_raises_when_the_first_version_is_unusable(tmp_path: Path) -> None:
    broken = "20261121T000000000000Z"
    (tmp_path / broken).mkdir()
    write_current(tmp_path, broken)
    current = CurrentStore(tmp_path, COLLECTION)
    with pytest.raises(IndexNotFoundError):
        current.get()


def test_current_store_closes_the_retired_store_on_the_next_swap(tmp_path: Path) -> None:
    current = CurrentStore(tmp_path, COLLECTION)
    try:
        for day, n in ((21, 1), (22, 2), (23, 3)):
            _build_version(tmp_path, f"202611{day}T000000000000Z", CHUNKS[:n])
            assert current.get().count() == n
        # the first version was closed, so it can be pruned even on Windows
        assert prune_versions(tmp_path, keep=2) == ["20261121T000000000000Z"]
    finally:
        current.close()
