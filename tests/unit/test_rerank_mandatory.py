"""RN-03 (KB-011) with the cross-encoder: scoring outside candidates, noise veto factor, config."""

from __future__ import annotations

import math
import re
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import pytest
import yaml

from src.chunking.section_chunker import Chunk, ChunkMetadata
from src.llm import NoLLM
from src.retrieval import AnswerService, Retriever
from src.retrieval.reranker import FastEmbedReranker
from src.utils.config import PROJECT_ROOT, ConfigError, Settings, load_settings
from src.vectordb import InMemoryVectorStore

QUERY = "consulta-unica-zq81"
MIN = 0.01
SAFE = "el sistema de caja marca error"  # cash_system regex
FRAUD = "creo que hay un fraude en la cuenta de un cliente"
DOC = PROJECT_ROOT / "docs" / "research" / "rejection-experiment.md"


def _vec(cos: float) -> list[float]:
    return [cos, math.sqrt(1 - cos * cos), 0.0]


class _Embedder:
    dimension = 3

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        raise AssertionError("not used")

    def embed_query(self, text: str) -> list[float]:
        return [1.0, 0.0, 0.0]


class FakeReranker:
    def __init__(self, scores: dict[str, float]) -> None:
        self.scores = scores
        self.calls: list[list[str]] = []

    def score(self, query: str, passages: list[str]) -> list[float]:
        self.calls.append(passages)
        out = []
        for passage in passages:
            match = re.search(r"KB-\d{3}", passage)
            assert match is not None
            out.append(self.scores[match.group(0)])
        return out

    def warm(self) -> None:
        pass


class RecordingLLM:
    provider = "fake"

    def __init__(self) -> None:
        self.users: list[str] = []

    def generate(self, system: str, user: str, timeout_s: float) -> str:
        self.users.append(user)
        return "1. Espera 15 minutos."


def _chunk(article_id: str) -> Chunk:
    return Chunk(
        chunk_id=f"{article_id}#sintoma#0",
        text=f"Titulo {article_id} — sintoma\ntexto de {article_id}",
        metadata=ChunkMetadata(
            article_id=article_id,
            titulo=f"Titulo {article_id}",
            categoria="Accesos",
            subcategoria="Sub",
            idioma="es",
            seccion="sintoma",
            palabras_clave="",
            source=f"{article_id}.md",
        ),
    )


def _retriever(
    cosines: dict[str, float], reranker: Any, *, min_score: float = MIN, candidates: int = 3
) -> Retriever:
    store = InMemoryVectorStore()
    store.upsert([_chunk(a) for a in cosines], [_vec(c) for c in cosines.values()])
    return Retriever(
        _Embedder(),
        store,
        top_k=3,
        threshold=0.3,
        reranker=reranker,
        rerank_min_score=min_score,
        rerank_candidates=candidates,
    )


def _settings(tmp_path: Path, **rerank: Any) -> Settings:
    data = yaml.safe_load((PROJECT_ROOT / "config.yaml").read_text(encoding="utf-8"))
    data["retrieval"]["rerank"].update({"min_score": MIN, **rerank})
    path = tmp_path / "config.yaml"
    path.write_text(yaml.safe_dump(data, allow_unicode=True), encoding="utf-8")
    return load_settings(path, env_file=tmp_path / "missing.env")


# KB-011 is third (outside the single candidate) but still inside the cosine margin of the top.
OUTSIDE = {"KB-002": 0.90, "KB-004": 0.89, "KB-011": 0.88}
CAJA = {"KB-002": 0.9, "KB-011": 0.88}


# --- (1) KB-011 is scored even outside the candidates -------------------------------------


def test_rerank_scores_include_kb011_outside_the_candidates() -> None:
    fake = FakeReranker({"KB-002": 0.5, "KB-004": 0.4, "KB-011": 0.3})
    result = _retriever(OUTSIDE, fake, candidates=1).search(QUERY)
    assert result.rerank_scores == {"KB-002": 0.5, "KB-011": 0.3}
    assert "KB-004" not in result.rerank_scores  # non-mandatory articles outside stay unscored


def test_kb011_outside_the_candidates_does_not_enter_the_global_veto() -> None:
    fake = FakeReranker({"KB-002": 0.0001, "KB-004": 0.0001, "KB-011": 0.99})
    result = _retriever(OUTSIDE, fake, candidates=1).search(QUERY)
    assert result.rerank_score == pytest.approx(0.0001)
    assert result.vetoed  # a high KB-011 score must not rescue a noisy query


def test_no_extra_scoring_when_kb011_is_not_retrieved() -> None:
    fake = FakeReranker({"KB-002": 0.5, "KB-004": 0.4, "KB-006": 0.3})
    result = _retriever({"KB-002": 0.9, "KB-004": 0.8, "KB-006": 0.7}, fake, candidates=1).search(
        QUERY
    )
    assert set(result.rerank_scores) == {"KB-002"}


class _Model:
    def __init__(self) -> None:
        self.calls: list[list[str]] = []

    def rerank(self, query: str, documents: Sequence[str]) -> list[float]:
        self.calls.append(list(documents))
        return [0.0] * len(documents)


def test_reranker_is_called_one_passage_per_call_including_kb011() -> None:
    model = _Model()
    reranker = FastEmbedReranker("fake-model")
    reranker._model = model  # type: ignore[assignment]
    _retriever(OUTSIDE, reranker, candidates=1).search(QUERY)
    assert [len(docs) for docs in model.calls] == [1, 1]
    assert "KB-011" in model.calls[1][0]


# --- (2) veto factor on KB-011 ------------------------------------------------------------


def _answer(
    tmp_path: Path, kb011: float, factor: float, llm: Any = None, query: str = QUERY
) -> Any:
    settings = _settings(tmp_path, mandatory_veto_factor=factor)
    fake = FakeReranker({"KB-002": 0.5, "KB-011": kb011})
    return AnswerService(_retriever(CAJA, fake), llm or NoLLM(), settings).answer(query)


@pytest.mark.parametrize("factor", [0.1, 1.0])
def test_kb011_far_below_the_cutoff_is_dropped_everywhere(tmp_path: Path, factor: float) -> None:
    llm = RecordingLLM()
    answer = _answer(tmp_path, MIN * factor * 0.05, factor, llm)
    assert answer.status == "answered"
    assert [c.article_id for c in answer.citations] == ["KB-002"]
    assert len(llm.users) == 1 and "KB-011" not in llm.users[0]
    assert "KB-011" not in answer.text


def test_kb011_at_0_005_of_min_score_is_dropped_and_at_0_2_escalates(tmp_path: Path) -> None:
    assert _answer(tmp_path, MIN * 0.005, 0.1).status == "answered"
    escalated = _answer(tmp_path, MIN * 0.2, 0.1)
    assert escalated.status == "mandatory_escalation"
    assert [c.article_id for c in escalated.citations] == ["KB-011"]


@pytest.mark.parametrize("factor", [0.1, 0.5, 1.0])
def test_exact_cutoff_escalates_and_just_below_is_dropped(tmp_path: Path, factor: float) -> None:
    cutoff = MIN * factor
    assert _answer(tmp_path, cutoff, factor).status == "mandatory_escalation"
    assert _answer(tmp_path, math.nextafter(cutoff, 0.0), factor).status == "answered"


def test_factor_changes_the_verdict_for_the_same_score(tmp_path: Path) -> None:
    score = MIN * 0.5
    assert _answer(tmp_path, score, 0.1).status == "mandatory_escalation"
    assert _answer(tmp_path, score, 1.0).status == "answered"


def test_kb011_without_a_score_is_not_vetoed(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    answer = AnswerService(_retriever(CAJA, None), NoLLM(), settings).answer(QUERY)
    assert answer.status == "mandatory_escalation"


# --- (3) model allow-list -----------------------------------------------------------------


@pytest.mark.parametrize("model", ["BAAI/bge-reranker-base", "other", "", "  ", None])
@pytest.mark.parametrize("enabled", [True, False])
def test_unsupported_model_fails_fast_with_a_clear_message(
    tmp_path: Path, model: Any, enabled: bool
) -> None:
    with pytest.raises(ConfigError) as info:
        _settings(tmp_path, enabled=enabled, model=model)
    message = str(info.value)
    assert "retrieval.rerank.model" in message and "not supported" in message
    assert "BAAI/bge-reranker-v2-m3-int8" in message


def test_allowed_model_is_accepted(tmp_path: Path) -> None:
    rerank = _settings(tmp_path, model="BAAI/bge-reranker-v2-m3-int8").retrieval.rerank
    assert rerank.model == "BAAI/bge-reranker-v2-m3-int8"


# --- (4) factor range ---------------------------------------------------------------------


@pytest.mark.parametrize("bad", [-0.1, -1, 1.0001, 2, "x", None])
def test_mandatory_veto_factor_out_of_range_fails_at_startup(tmp_path: Path, bad: Any) -> None:
    with pytest.raises(ConfigError, match="mandatory_veto_factor"):
        _settings(tmp_path, mandatory_veto_factor=bad)


@pytest.mark.parametrize("ok", [0.0001, 0.1, 1.0])
def test_mandatory_veto_factor_valid_values(tmp_path: Path, ok: float) -> None:
    rerank = _settings(tmp_path, mandatory_veto_factor=ok).retrieval.rerank
    assert rerank.mandatory_veto_factor == ok


def test_mandatory_veto_factor_zero_is_accepted_and_disables_the_noise_veto(
    tmp_path: Path,
) -> None:
    # Current behaviour (ge=0.0): 0 is the documented "no veto" setting of the experiment.
    # The requested range was 0 < f <= 1; see the QA report before tightening the schema.
    settings = _settings(tmp_path, mandatory_veto_factor=0.0)
    assert settings.retrieval.rerank.mandatory_veto_factor == 0.0
    assert _answer(tmp_path, 0.0, 0.0).status == "mandatory_escalation"


def test_repo_default_factor_is_0_1(tmp_path: Path) -> None:
    settings = load_settings(env_file=tmp_path / "x.env")
    assert settings.retrieval.rerank.mandatory_veto_factor == 0.1


# --- (5) RN-03 regression: the veto never silences the keyword regex ----------------------


@pytest.mark.parametrize("query", [SAFE, FRAUD])
@pytest.mark.parametrize("factor", [0.1, 1.0])
@pytest.mark.parametrize("with_kb011", [True, False])
def test_aggressive_veto_never_silences_the_regex(
    tmp_path: Path, query: str, factor: float, with_kb011: bool
) -> None:
    cosines = CAJA if with_kb011 else {"KB-002": 0.9, "KB-004": 0.8}
    fake = FakeReranker({"KB-002": 1e-9, "KB-004": 1e-9, "KB-011": 1e-9})
    settings = _settings(tmp_path, mandatory_veto_factor=factor)
    retriever = _retriever(cosines, fake)
    assert retriever.search(query).vetoed
    llm = RecordingLLM()
    answer = AnswerService(retriever, llm, settings).answer(query)
    assert answer.status == "mandatory_escalation"
    assert llm.users == []
    assert all(c.article_id == "KB-011" for c in answer.citations)


# --- (6) documented limit -----------------------------------------------------------------


def test_experiment_doc_records_the_factor_and_the_four_uncovered_paraphrases() -> None:
    text = DOC.read_text(encoding="utf-8")
    assert "mandatory_veto_factor" in text
    for case in ("CA-02", "CA-07", "CA-08", "CA-10"):
        assert case in text
    assert re.search(r"Escalan 8 de 12 par[aá]frasis; las 4 que no escalan", text)
    assert "margen de coseno" in text
