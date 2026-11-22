"""Cross-encoder veto (retrieval.rerank): behaviour with an injected fake, no model download."""

from __future__ import annotations

import csv
import difflib
import logging
import math
import re
import unicodedata
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any

import pytest
import yaml

from src.api.evaluation import load_cases
from src.chunking.section_chunker import Chunk, ChunkMetadata
from src.llm import NoLLM
from src.retrieval import AnswerService, Retriever
from src.retrieval.reranker import FastEmbedReranker, build_reranker, sigmoid
from src.utils.config import PROJECT_ROOT, ConfigError, Settings, load_settings
from src.vectordb import InMemoryVectorStore

QUERY = "consulta-unica-zq81"
HELDOUT = PROJECT_ROOT / "tests" / "eval" / "heldout_cases.csv"
CASES = PROJECT_ROOT / "tests" / "eval" / "cases.csv"
MIN = 0.004


def _vec(cos: float) -> list[float]:
    return [cos, math.sqrt(1 - cos * cos), 0.0]


class ScriptedEmbedder:
    dimension = 3

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        raise AssertionError("not used")

    def embed_query(self, text: str) -> list[float]:
        return [1.0, 0.0, 0.0]


class FakeReranker:
    """Scores each passage by the article id it mentions; records calls."""

    def __init__(self, scores: dict[str, float]) -> None:
        self.scores = scores
        self.calls: list[tuple[str, list[str]]] = []

    def score(self, query: str, passages: list[str]) -> list[float]:
        self.calls.append((query, passages))
        out = []
        for passage in passages:
            match = re.search(r"KB-\d{3}", passage)
            assert match is not None
            out.append(self.scores[match.group(0)])
        return out

    def warm(self) -> None:
        pass


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
    cosines: dict[str, float],
    reranker: FakeReranker | None,
    *,
    min_score: float = MIN,
    candidates: int = 3,
) -> Retriever:
    store = InMemoryVectorStore()
    chunks = [_chunk(a) for a in cosines]
    store.upsert(chunks, [_vec(c) for c in cosines.values()])
    return Retriever(
        ScriptedEmbedder(),
        store,
        top_k=3,
        threshold=0.3,
        reranker=reranker,
        rerank_min_score=min_score,
        rerank_candidates=candidates,
    )


COS = {"KB-002": 0.9, "KB-004": 0.7, "KB-006": 0.5}


def _repo_settings(tmp_path: Path) -> Settings:
    return load_settings(env_file=tmp_path / "missing.env")


# --- veto only below min_score; never reorders --------------------------------------------


@pytest.mark.parametrize(
    ("best", "vetoed"), [(0.0039, True), (0.004, False), (0.0041, False), (0.9, False)]
)
def test_veto_only_when_best_score_is_below_min_score(best: float, vetoed: bool) -> None:
    fake = FakeReranker({"KB-002": best, "KB-004": 0.0001, "KB-006": 0.0001})
    result = _retriever(COS, fake).search(QUERY)
    assert result.vetoed is vetoed
    assert result.rerank_score == pytest.approx(best)
    assert result.has_evidence  # the embedding threshold alone is untouched


def test_best_of_the_candidates_counts_not_just_the_top_one() -> None:
    fake = FakeReranker({"KB-002": 0.0001, "KB-004": 0.5, "KB-006": 0.0001})
    result = _retriever(COS, fake).search(QUERY)
    assert not result.vetoed
    assert result.low_rerank == {"KB-002", "KB-006"}


def test_candidates_limits_how_many_articles_are_scored() -> None:
    fake = FakeReranker({"KB-002": 0.5, "KB-004": 0.5, "KB-006": 0.5})
    _retriever(COS, fake, candidates=1).search(QUERY)
    assert len(fake.calls[0][1]) == 1 and "KB-002" in fake.calls[0][1][0]


def test_reranker_never_reorders_or_drops_articles() -> None:
    inverted = FakeReranker({"KB-002": 0.0001, "KB-004": 0.2, "KB-006": 0.99})
    with_rr = _retriever(COS, inverted).search(QUERY)
    without = _retriever(COS, None).search(QUERY)
    assert [a.article_id for a in with_rr.articles] == ["KB-002", "KB-004", "KB-006"]
    assert [(a.article_id, a.score) for a in with_rr.articles] == [
        (a.article_id, a.score) for a in without.articles
    ]


def test_not_scored_when_embedding_score_is_below_the_threshold() -> None:
    fake = FakeReranker({"KB-002": 0.5})
    result = _retriever({"KB-002": 0.1}, fake).search(QUERY)
    assert fake.calls == [] and result.rerank_score is None and not result.vetoed


# --- disabled => previous behaviour --------------------------------------------------------


def test_without_a_reranker_nothing_is_vetoed() -> None:
    result = _retriever(COS, None).search(QUERY)
    assert result.rerank_score is None and not result.vetoed and result.low_rerank == set()


def test_answer_is_no_evidence_when_vetoed_and_answered_otherwise(tmp_path: Path) -> None:
    settings = _repo_settings(tmp_path)
    low = FakeReranker({a: 0.001 for a in COS})
    high = FakeReranker({a: 0.5 for a in COS})
    vetoed = AnswerService(_retriever(COS, low), NoLLM(), settings).answer(QUERY)
    plain = AnswerService(_retriever(COS, None), NoLLM(), settings).answer(QUERY)
    allowed = AnswerService(_retriever(COS, high), NoLLM(), settings).answer(QUERY)
    assert vetoed.status == "no_evidence" and vetoed.citations == []
    assert plain.status == "answered" and allowed.status == "answered"
    assert allowed.text == plain.text


# --- embeddings fake / disabled => no reranker --------------------------------------------


def _settings(tmp_path: Path, **overrides: Any) -> Settings:
    data = yaml.safe_load((PROJECT_ROOT / "config.yaml").read_text(encoding="utf-8"))
    data["retrieval"]["rerank"].update(overrides.pop("rerank", {}))
    for section, values in overrides.items():
        data[section].update(values)
    path = tmp_path / "config.yaml"
    path.write_text(yaml.safe_dump(data, allow_unicode=True), encoding="utf-8")
    return load_settings(path, env_file=tmp_path / "missing.env")


def test_repo_config_enables_the_reranker_with_documented_values(tmp_path: Path) -> None:
    rerank = _repo_settings(tmp_path).retrieval.rerank
    assert rerank.enabled and rerank.min_score == 0.01 and rerank.candidates == 3
    assert rerank.model == "BAAI/bge-reranker-v2-m3-int8"


def test_build_reranker_is_none_with_fake_embeddings(tmp_path: Path) -> None:
    settings = _settings(tmp_path, embeddings={"provider": "fake"})
    assert settings.retrieval.rerank.enabled
    assert build_reranker(settings) is None


def test_build_reranker_is_none_when_disabled(tmp_path: Path) -> None:
    assert build_reranker(_settings(tmp_path, rerank={"enabled": False})) is None


def test_build_reranker_does_not_load_the_model(tmp_path: Path) -> None:
    reranker = build_reranker(_settings(tmp_path))
    assert isinstance(reranker, FastEmbedReranker)
    assert reranker._model is None  # lazy: the download happens in warm(), not here


def test_sigmoid_is_stable_and_monotonic() -> None:
    assert sigmoid(0.0) == 0.5
    assert sigmoid(-800.0) == 0.0 or 0.0 < sigmoid(-800.0) < 1e-300
    assert sigmoid(800.0) == 1.0
    assert sigmoid(-5.0) < sigmoid(-4.0) < sigmoid(3.0)


# --- Pydantic validation (fail fast) --------------------------------------------------------


@pytest.mark.parametrize(
    "bad",
    [
        {"min_score": -0.01},
        {"min_score": 1.01},
        {"candidates": 0},
        {"candidates": 11},
        {"enabled": True, "model": ""},
        {"enabled": True, "model": "   "},
        {"enabled": "maybe"},
        {"unknown_key": 1},
    ],
)
def test_invalid_rerank_config_fails_at_startup(tmp_path: Path, bad: dict[str, Any]) -> None:
    with pytest.raises(ConfigError, match="rerank"):
        _settings(tmp_path, rerank=bad)


@pytest.mark.parametrize("ok", [{"min_score": 0.0}, {"min_score": 1.0}, {"candidates": 1}])
def test_boundary_values_are_accepted(tmp_path: Path, ok: dict[str, Any]) -> None:
    assert _settings(tmp_path, rerank=ok).retrieval.rerank.enabled


# --- KB-011 escalation must pass the reranker ---------------------------------------------

CAJA = {"KB-002": 0.9, "KB-011": 0.88}  # KB-011 within the escalation margin of the top-1


def test_kb011_escalates_when_it_passes_the_reranker(tmp_path: Path) -> None:
    fake = FakeReranker({"KB-002": 0.5, "KB-011": 0.5})
    answer = AnswerService(_retriever(CAJA, fake), NoLLM(), _repo_settings(tmp_path)).answer(QUERY)
    assert answer.status == "mandatory_escalation"
    assert [c.article_id for c in answer.citations] == ["KB-011"]


def test_kb011_does_not_escalate_when_the_reranker_scores_it_low(tmp_path: Path) -> None:
    fake = FakeReranker({"KB-002": 0.5, "KB-011": 0.0001})
    answer = AnswerService(_retriever(CAJA, fake), NoLLM(), _repo_settings(tmp_path)).answer(QUERY)
    assert answer.status == "answered"
    assert [c.article_id for c in answer.citations] == ["KB-002"]


def test_kb011_escalates_without_a_reranker(tmp_path: Path) -> None:
    answer = AnswerService(_retriever(CAJA, None), NoLLM(), _repo_settings(tmp_path)).answer(QUERY)
    assert answer.status == "mandatory_escalation"


# --- logs: no query text --------------------------------------------------------------------


def test_logs_never_contain_the_query_text(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    fake = FakeReranker({a: 0.001 for a in COS})
    with caplog.at_level(logging.DEBUG):
        AnswerService(_retriever(COS, fake), NoLLM(), _repo_settings(tmp_path)).answer(QUERY)
    record = next(r for r in caplog.records if r.getMessage() == "Answer produced")
    assert record.__dict__["vetoed"] is True
    assert record.__dict__["rerank_score"] == 0.001
    assert all(QUERY not in str(r.__dict__) and QUERY not in r.getMessage() for r in caplog.records)


# --- held-out CSV -----------------------------------------------------------------------------


def _rows() -> list[dict[str, str]]:
    with HELDOUT.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def test_heldout_header_and_loader() -> None:
    with HELDOUT.open(encoding="utf-8-sig", newline="") as handle:
        header = next(csv.reader(handle))
    assert header == ["id", "pregunta", "intencion", "esperado", "obtenido", "resultado", "notas"]
    assert len(load_cases(HELDOUT)) == len(_rows())


def test_heldout_has_40_unique_cases_split_20_20() -> None:
    rows = _rows()
    ids = [r["id"] for r in rows]
    assert len(rows) >= 40 and len(set(ids)) == len(ids)
    assert all(re.fullmatch(r"HO-\d{2}", i) for i in ids)
    inside = [r for r in rows if r["esperado"].startswith("articulo:KB-")]
    outside = [r for r in rows if r["esperado"] == "rechazo"]
    assert len(inside) == 20 and len(outside) == 20
    assert len({r["esperado"] for r in inside}) >= 10
    assert all(r["obtenido"] == "" and r["resultado"] == "" for r in rows)


def test_heldout_labels_point_to_real_articles() -> None:
    kb = {p.name[:6] for p in (PROJECT_ROOT / "data" / "knowledge_base").glob("KB-*.md")}
    for r in _rows():
        if r["esperado"].startswith("articulo:"):
            assert r["esperado"].removeprefix("articulo:") in kb, r["id"]


def test_heldout_is_disjoint_from_the_canonical_and_rejection_cases() -> None:
    def questions(path: Path) -> set[str]:
        with path.open(encoding="utf-8-sig", newline="") as handle:
            return {r["pregunta"].strip().lower() for r in csv.DictReader(handle)}

    held = questions(HELDOUT)
    assert not held & questions(CASES)
    assert not held & questions(HELDOUT.with_name("rejection_cases.csv"))


def test_heldout_mixes_spanish_and_english() -> None:
    spanish = re.compile(r"[¿áéíóúñ]|\b(el|la|mi|mis|me|no|en|del|una?|que|ke)\b", re.IGNORECASE)
    english = re.compile(r"\b(the|my|how|is|do|not|can|for|will|it|says)\b", re.IGNORECASE)
    rows = _rows()
    assert sum(bool(spanish.search(r["pregunta"])) for r in rows) >= 10
    assert sum(bool(english.search(r["pregunta"])) for r in rows) >= 10


# --- one passage per forward pass (int8 scores depend on the batch) -----------------------

Q1 = "no puedo entrar a mi cuenta, se me bloqueo la contrasena"
ALONE_Q1, BATCHED_Q1 = 0.0481, 0.0192  # measured with the real int8 model for Q1 + KB-002
OLD_MIN = 0.02  # the previous config value: 0.0192 was vetoed, 0.0481 was not


def _logit(p: float) -> float:
    return math.log(p / (1.0 - p))


class BatchSensitiveModel:
    """Stands in for the int8 cross-encoder: the score of a passage depends on the batch size."""

    def __init__(self, alone: float, batched: float) -> None:
        self.alone, self.batched = alone, batched
        self.calls: list[tuple[str, list[str]]] = []

    def rerank(self, query: str, documents: Sequence[str]) -> list[float]:
        self.calls.append((query, list(documents)))
        p = self.alone if len(documents) == 1 else self.batched
        return [_logit(p)] * len(documents)


def _fastembed(model: BatchSensitiveModel) -> FastEmbedReranker:
    reranker = FastEmbedReranker("fake-model")
    reranker._model = model  # type: ignore[assignment]
    return reranker


def test_reranker_scores_exactly_one_passage_per_call() -> None:
    model = BatchSensitiveModel(ALONE_Q1, BATCHED_Q1)
    scores = _fastembed(model).score(Q1, ["KB-002 a", "KB-004 b", "KB-006 c"])
    assert [len(docs) for _, docs in model.calls] == [1, 1, 1]
    assert [docs[0] for _, docs in model.calls] == ["KB-002 a", "KB-004 b", "KB-006 c"]
    assert scores == [pytest.approx(ALONE_Q1)] * 3


def test_reranker_with_no_passages_makes_no_call() -> None:
    model = BatchSensitiveModel(ALONE_Q1, BATCHED_Q1)
    assert _fastembed(model).score(Q1, []) == []
    assert model.calls == []


@pytest.mark.parametrize("others", [0, 1, 2, 7])
def test_score_of_a_passage_does_not_depend_on_the_other_passages(others: int) -> None:
    model = BatchSensitiveModel(ALONE_Q1, BATCHED_Q1)
    reranker = _fastembed(model)
    isolated = reranker.score(Q1, ["KB-002 a"])[0]
    accompanied = reranker.score(Q1, ["KB-002 a", *[f"KB-0{i} x" for i in range(others)]])[0]
    assert isolated == accompanied == pytest.approx(ALONE_Q1)


def _retriever_with_model(model: BatchSensitiveModel, min_score: float) -> Retriever:
    return _retriever(COS, _fastembed(model), min_score=min_score)  # type: ignore[arg-type]


def test_q1_without_accents_is_answered_with_the_isolated_score(tmp_path: Path) -> None:
    model = BatchSensitiveModel(ALONE_Q1, BATCHED_Q1)
    retriever = _retriever_with_model(model, 0.01)
    result = retriever.search(Q1)
    assert result.rerank_score == pytest.approx(ALONE_Q1) and not result.vetoed
    answer = AnswerService(retriever, NoLLM(), _repo_settings(tmp_path)).answer(Q1)
    assert answer.status == "answered"
    assert answer.citations[0].article_id == "KB-002"


def test_q1_regression_isolated_score_passes_where_the_batched_one_was_vetoed() -> None:
    # With the old batched scoring 0.0192 < 0.02 vetoed Q1; scoring alone gives 0.0481 >= 0.02.
    assert BATCHED_Q1 < OLD_MIN <= ALONE_Q1
    assert (
        not _retriever_with_model(BatchSensitiveModel(ALONE_Q1, BATCHED_Q1), OLD_MIN)
        .search(Q1)
        .vetoed
    )
    # A model that really scored 0.0192 is still vetoed at that threshold: the veto is intact.
    assert (
        _retriever_with_model(BatchSensitiveModel(BATCHED_Q1, BATCHED_Q1), OLD_MIN)
        .search(Q1)
        .vetoed
    )


def test_score_exactly_equal_to_min_score_is_not_vetoed() -> None:
    fake = FakeReranker({"KB-002": 0.01, "KB-004": 0.0001, "KB-006": 0.0001})
    assert not _retriever(COS, fake, min_score=0.01).search(QUERY).vetoed
    below = FakeReranker({"KB-002": 0.0099, "KB-004": 0.0001, "KB-006": 0.0001})
    assert _retriever(COS, below, min_score=0.01).search(QUERY).vetoed


def test_disabled_rerank_keeps_the_previous_behaviour(tmp_path: Path) -> None:
    settings = _settings(tmp_path, rerank={"enabled": False})
    assert build_reranker(settings) is None
    answer = AnswerService(_retriever(COS, None), NoLLM(), settings).answer(Q1)
    assert answer.status == "answered"


# --- robustness to query variants (fake reranker that reads the query) --------------------

IN_DOMAIN = {
    "KB-002": [
        "No puedo iniciar sesión, olvidé mi contraseña",
        "Se me bloqueó la cuenta después de varios intentos",
    ]
}
THRESHOLD = 0.01


def _fold(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", text.lower())
    return "".join(c for c in decomposed if not unicodedata.combining(c))


def _typo(text: str) -> str:
    """Deterministic typo: swap the two middle characters of every word of 6+ letters."""
    words = []
    for word in text.split():
        if len(word) >= 6:
            mid = len(word) // 2
            word = word[: mid - 1] + word[mid] + word[mid - 1] + word[mid + 1 :]
        words.append(word)
    return " ".join(words)


class FuzzyQueryReranker(FakeReranker):
    """Scores 0.05 when the (folded, fuzzy) query tokens match the in-domain text, else 1e-4."""

    def __init__(self, reference: str) -> None:
        super().__init__({})
        self.reference = set(_fold(reference).replace(",", "").split())

    def score(self, query: str, passages: list[str]) -> list[float]:
        self.calls.append((query, passages))
        tokens = _fold(query).replace(",", "").split()
        hits = sum(
            bool(difflib.get_close_matches(t, self.reference, n=1, cutoff=0.8)) for t in tokens
        )
        return [0.05 if hits / len(tokens) >= 0.5 else 0.0001 for _ in passages]


VARIANTS: dict[str, Callable[[str], str]] = {
    "original": lambda q: q,
    "lowercase": str.lower,
    "uppercase": str.upper,
    "unaccented": _fold,
    "typo": _typo,
    "unaccented_typo": lambda q: _typo(_fold(q)),
}


@pytest.mark.parametrize("variant", VARIANTS)
@pytest.mark.parametrize("query", [q for qs in IN_DOMAIN.values() for q in qs])
def test_in_domain_variants_are_not_vetoed(query: str, variant: str) -> None:
    fake = FuzzyQueryReranker(" ".join(IN_DOMAIN["KB-002"]))
    text = VARIANTS[variant](query)
    result = _retriever(COS, fake, min_score=THRESHOLD).search(text)
    assert result.rerank_score is not None and result.rerank_score >= THRESHOLD
    assert not result.vetoed


def test_out_of_domain_query_is_still_vetoed_by_the_same_fake() -> None:
    fake = FuzzyQueryReranker(" ".join(IN_DOMAIN["KB-002"]))
    assert _retriever(COS, fake, min_score=THRESHOLD).search("receta de paella valenciana").vetoed


# --- optional, with the real model (run with: pytest -m slow) ---------------------------------


@pytest.mark.slow
def test_real_model_separates_relevant_from_irrelevant(tmp_path: Path) -> None:
    reranker = build_reranker(_repo_settings(tmp_path))
    assert reranker is not None
    relevant, irrelevant = reranker.score(
        "No puedo iniciar sesión porque olvidé mi contraseña de Windows",
        [
            "Restablecer la contraseña de red — sintoma\nNo puedes iniciar sesión en Windows "
            "porque olvidaste tu contraseña.",
            "La impresora no imprime — sintoma\nLos documentos se quedan en la cola.",
        ],
    )
    assert relevant > MIN > 0 and relevant > irrelevant


@pytest.mark.slow
def test_real_model_answers_q1_without_accents_with_kb002() -> None:
    from src.api.app import build_services

    services = build_services(load_settings())
    try:
        answer = services.answers.answer(Q1)
    finally:
        services.close()
    assert answer.status == "answered"
    assert answer.citations[0].article_id == "KB-002"
