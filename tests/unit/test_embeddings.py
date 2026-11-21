"""Unit tests for src/embeddings: deterministic fake, fastembed wrapper and factory."""

from __future__ import annotations

import math
import sys
import types
from collections.abc import Iterable, Iterator
from pathlib import Path
from typing import Any

import numpy as np
import pytest

from src.embeddings import (
    Embedder,
    FakeEmbedder,
    FastEmbedEmbedder,
    build_embedder,
    normalize_tokens,
)
from src.utils.config import EmbeddingsConfig, Settings, load_settings

MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"


def _cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    norm = math.sqrt(sum(x * x for x in a)) * math.sqrt(sum(y * y for y in b))
    return dot / norm if norm else 0.0


def _settings(tmp_path: Path, **embeddings: Any) -> Settings:
    settings = load_settings(env_file=tmp_path / "missing.env")
    config = settings.embeddings.model_copy(update=embeddings)
    return settings.model_copy(update={"embeddings": config})


# --- FakeEmbedder -----------------------------------------------------------------------


def test_normalize_tokens_lowercases_strips_accents_and_short_tokens() -> None:
    assert normalize_tokens("Se BLOQUEÓ mi usuario, ¡Contraseña!") == [
        "bloqueo",
        "usuario",
        "contrasena",
    ]


def test_fake_embedder_is_deterministic_and_has_the_declared_dimension() -> None:
    first = FakeEmbedder(dimension=64).embed_documents(["usuario bloqueado", "VPN"])
    second = FakeEmbedder(dimension=64).embed_documents(["usuario bloqueado", "VPN"])
    assert first == second
    assert all(len(vector) == 64 for vector in first)
    assert FakeEmbedder(dimension=64).dimension == 64


def test_fake_embedder_returns_unit_vectors() -> None:
    vector = FakeEmbedder().embed_query("la impresora no imprime")
    assert math.isclose(math.sqrt(sum(x * x for x in vector)), 1.0)


def test_fake_embedder_ignores_case_and_accents() -> None:
    embedder = FakeEmbedder()
    assert embedder.embed_query("Contraseña BLOQUEADA") == embedder.embed_query(
        "contrasena bloqueada"
    )


def test_texts_sharing_words_are_more_similar_than_unrelated_texts() -> None:
    embedder = FakeEmbedder()
    query = embedder.embed_query("mi usuario de Windows está bloqueado")
    related, unrelated = embedder.embed_documents(
        ["Desbloqueo de usuario de Windows bloqueado", "La impresora no imprime en red"]
    )
    assert _cosine(query, related) > 0.5
    assert _cosine(query, related) > _cosine(query, unrelated)


def test_fake_embedder_maps_text_without_tokens_to_the_zero_vector() -> None:
    assert FakeEmbedder(dimension=8).embed_query("¡¿ !?") == [0.0] * 8


def test_fake_embedder_rejects_a_non_positive_dimension() -> None:
    with pytest.raises(ValueError, match="dimension"):
        FakeEmbedder(dimension=0)


def test_fake_embedder_satisfies_the_protocol() -> None:
    assert isinstance(FakeEmbedder(), Embedder)


# --- FastEmbedEmbedder (fastembed mocked: no download) ----------------------------------


class _FakeTextEmbedding:
    """Stand-in for ``fastembed.TextEmbedding``; records how it was built and used."""

    instances: list[_FakeTextEmbedding] = []

    def __init__(self, model_name: str, cache_dir: str | None = None) -> None:
        self.model_name = model_name
        self.cache_dir = cache_dir
        self.queries: list[str] = []
        _FakeTextEmbedding.instances.append(self)

    @staticmethod
    def get_embedding_size(model_name: str) -> int:
        return 3

    def embed(self, documents: Iterable[str]) -> Iterator[np.ndarray]:
        for _ in documents:
            yield np.array([3.0, 4.0, 0.0], dtype=np.float32)

    def query_embed(self, query: str) -> Iterator[np.ndarray]:
        self.queries.append(query)
        yield np.array([0.0, 0.0, 2.0], dtype=np.float32)


@pytest.fixture
def fake_fastembed(monkeypatch: pytest.MonkeyPatch) -> type[_FakeTextEmbedding]:
    module = types.ModuleType("fastembed")
    module.TextEmbedding = _FakeTextEmbedding  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "fastembed", module)
    _FakeTextEmbedding.instances = []
    return _FakeTextEmbedding


def test_fastembed_model_is_loaded_lazily_once(
    fake_fastembed: type[_FakeTextEmbedding], tmp_path: Path
) -> None:
    embedder = FastEmbedEmbedder(MODEL, cache_dir=tmp_path / "cache")
    assert fake_fastembed.instances == []
    embedder.embed_documents(["a"])
    embedder.embed_query("b")
    assert len(fake_fastembed.instances) == 1
    assert fake_fastembed.instances[0].model_name == MODEL
    assert fake_fastembed.instances[0].cache_dir == str(tmp_path / "cache")


def test_fastembed_vectors_are_l2_normalized_python_floats(
    fake_fastembed: type[_FakeTextEmbedding],
) -> None:
    embedder = FastEmbedEmbedder(MODEL)
    documents = embedder.embed_documents(["uno", "dos"])
    assert documents == [[0.6, 0.8, 0.0], [0.6, 0.8, 0.0]]
    assert all(type(x) is float for x in documents[0])
    assert embedder.embed_query("tres") == [0.0, 0.0, 1.0]
    assert fake_fastembed.instances[0].queries == ["tres"]


def test_fastembed_dimension_does_not_load_the_model(
    fake_fastembed: type[_FakeTextEmbedding],
) -> None:
    assert FastEmbedEmbedder(MODEL).dimension == 3
    assert fake_fastembed.instances == []


def test_fastembed_empty_input_returns_no_vectors(
    fake_fastembed: type[_FakeTextEmbedding],
) -> None:
    assert FastEmbedEmbedder(MODEL).embed_documents([]) == []
    assert fake_fastembed.instances == []


def test_fastembed_missing_package_raises_a_clear_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(sys.modules, "fastembed", None)
    with pytest.raises(RuntimeError, match="pip install"):
        FastEmbedEmbedder(MODEL).embed_query("hola")


# --- build_embedder ---------------------------------------------------------------------


def test_build_embedder_fake(tmp_path: Path) -> None:
    assert isinstance(build_embedder(_settings(tmp_path, provider="fake")), FakeEmbedder)


def test_build_embedder_fastembed_uses_model_and_cache_dir_from_config(
    tmp_path: Path, fake_fastembed: type[_FakeTextEmbedding]
) -> None:
    settings = _settings(tmp_path, provider="fastembed", cache_dir=tmp_path / "models")
    embedder = build_embedder(settings)
    assert isinstance(embedder, FastEmbedEmbedder)
    assert embedder.model_name == MODEL
    assert embedder.cache_dir == tmp_path / "models"


def test_build_embedder_accepts_the_embeddings_section() -> None:
    config = EmbeddingsConfig(provider="fake", model="any")
    assert isinstance(build_embedder(config), FakeEmbedder)


# --- Real model (downloads ~250 MB; run with: pytest -m slow) ---------------------------


@pytest.mark.slow
def test_real_fastembed_model_is_multilingual_and_384_dimensional() -> None:
    settings = load_settings()
    embedder = FastEmbedEmbedder(settings.embeddings.model, settings.embeddings.cache_dir)
    assert embedder.dimension == 384
    query_es = embedder.embed_query("se bloqueó mi usuario de Windows")
    unlock, vpn = embedder.embed_documents(
        ["Desbloqueo de usuario de Windows", "La VPN no conecta desde casa"]
    )
    assert len(query_es) == 384
    assert _cosine(query_es, unlock) > _cosine(query_es, vpn)
    query_en = embedder.embed_query("my VPN does not connect")
    assert _cosine(query_en, vpn) > _cosine(query_en, unlock)
