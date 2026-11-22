"""Unit tests for the answer service: every branch of the decision (S7, RF-04/05/10/14, RN-03)."""

from __future__ import annotations

import logging
from pathlib import Path

import pytest

from src.chunking.section_chunker import Chunk, ChunkMetadata
from src.embeddings import FakeEmbedder
from src.llm import LLMError, LLMTimeoutError, NoLLM
from src.prompts import ANSWER_WITH_CITATION, NO_EVIDENCE_TOKEN
from src.retrieval import (
    AnswerService,
    Retriever,
    detect_language,
    escalation_reason,
    format_steps,
)
from src.utils.config import Settings, load_settings
from src.vectordb import InMemoryVectorStore

PASSWORD = "Sol2024!xyz"
SOURCE_ES = "Fuente: KB-002 — Desbloquear un usuario de red"

ARTICLES: dict[str, tuple[str, str, dict[str, str]]] = {
    "KB-002": (
        "Desbloquear un usuario de red",
        "Accesos",
        {
            "sintoma": "Windows dice que tu usuario esta bloqueado (account locked user).",
            "pasos": "1. Espera 15 minutos.\n2. Usa Desbloquear mi cuenta con tu numero.",
            "cuando_escalar": "Escala como P2 si la cuenta se vuelve a bloquear.",
        },
    ),
    "KB-004": (
        "VPN que no conecta",
        "Red",
        {
            "sintoma": "La VPN no conecta desde casa (VPN does not connect).",
            "pasos": "1. Revisa tu internet.\n2. Reinicia el cliente VPN.",
        },
    ),
    "KB-011": (
        "Falla en la terminal de ventanilla",
        "Hardware",
        {
            "sintoma": "La terminal se congela con efectivo en ventanilla.",
            "pasos": "1. Detén la operación.\n2. No reinicies la terminal.",
        },
    ),
    "KB-020": ("Escaner sin pasos", "Hardware", {"sintoma": "El escaner muestra luz roja."}),
}


def _chunks() -> list[Chunk]:
    chunks = []
    for article_id, (titulo, categoria, sections) in ARTICLES.items():
        for seccion, body in sections.items():
            chunks.append(
                Chunk(
                    chunk_id=f"{article_id}#{seccion}#0",
                    text=f"{titulo} — {seccion}\n{body}",
                    metadata=ChunkMetadata(
                        article_id=article_id,
                        titulo=titulo,
                        categoria=categoria,
                        subcategoria="Sub",
                        idioma="es",
                        seccion=seccion,
                        palabras_clave="",
                        source=f"{article_id}.md",
                    ),
                )
            )
    return chunks


class SpyEmbedder(FakeEmbedder):
    def __init__(self) -> None:
        super().__init__()
        self.queries: list[str] = []

    def embed_query(self, text: str) -> list[float]:
        self.queries.append(text)
        return super().embed_query(text)


class FakeLLM:
    provider = "fake"

    def __init__(self, reply: str = "", error: LLMError | None = None) -> None:
        self.reply = reply
        self.error = error
        self.calls: list[tuple[str, str, float]] = []

    def generate(self, system: str, user: str, timeout_s: float) -> str:
        self.calls.append((system, user, timeout_s))
        if self.error is not None:
            raise self.error
        return self.reply


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return load_settings(env_file=tmp_path / "missing.env")


@pytest.fixture
def embedder() -> SpyEmbedder:
    return SpyEmbedder()


@pytest.fixture
def retriever(embedder: SpyEmbedder) -> Retriever:
    store = InMemoryVectorStore()
    chunks = _chunks()
    store.upsert(chunks, embedder.embed_documents([c.text for c in chunks]))
    return Retriever(embedder, store, top_k=3, threshold=0.2)


def _service(retriever: Retriever, settings: Settings, llm: object | None = None) -> AnswerService:
    return AnswerService(retriever, llm or NoLLM(), settings)  # type: ignore[arg-type]


# --- extractive (provider none) ------------------------------------------------------


def test_extractive_answer_gives_numbered_steps_and_cites_the_article(
    retriever: Retriever, settings: Settings
) -> None:
    answer = _service(retriever, settings).answer("se bloqueó mi usuario de Windows")

    assert answer.status == "answered"
    assert answer.mode == "extractive"
    assert answer.language == "es"
    assert answer.prompt_key is None
    assert not answer.sensitive_data_warning
    assert answer.text.splitlines()[0] == (
        "Sigue estos pasos del artículo KB-002 — Desbloquear un usuario de red:"
    )
    assert "1. Espera 15 minutos.\n2. Usa Desbloquear mi cuenta con tu numero." in answer.text
    assert answer.text.endswith(SOURCE_ES)
    (citation,) = answer.citations
    assert citation.article_id == "KB-002"
    assert citation.titulo == "Desbloquear un usuario de red"
    assert 0.2 <= citation.similarity <= 1


def test_english_query_gets_english_framing_and_the_same_article(
    retriever: Retriever, settings: Settings
) -> None:
    answer = _service(retriever, settings).answer("my Windows user account is locked")

    assert answer.language == "en"
    assert answer.status == "answered"
    assert answer.text.startswith("Follow these steps from article KB-002")
    assert "steps are quoted as written" in answer.text  # known limitation: steps in Spanish
    assert "1. Espera 15 minutos." in answer.text
    assert answer.text.endswith("Source: KB-002 — Desbloquear un usuario de red")
    assert [c.article_id for c in answer.citations] == ["KB-002"]


def test_article_without_steps_falls_back_to_its_best_chunk(
    retriever: Retriever, settings: Settings
) -> None:
    answer = _service(retriever, settings).answer("el escaner muestra luz roja")
    assert answer.citations[0].article_id == "KB-020"
    assert "1. El escaner muestra luz roja." in answer.text


def test_no_llm_is_never_called(retriever: Retriever, settings: Settings) -> None:
    class Exploding(NoLLM):
        def generate(self, system: str, user: str, timeout_s: float) -> str:
            raise AssertionError("NoLLM must not be called")

    assert _service(retriever, settings, Exploding()).answer("VPN no conecta").mode == "extractive"


# --- no evidence ---------------------------------------------------------------------


@pytest.mark.parametrize(
    ("query", "prefix"),
    [
        ("receta de pozole", "No lo sé, escalo a un agente humano"),
        ("how do I bake a chocolate cake", "I don't know, I'm escalating to a human agent"),
    ],
)
def test_out_of_domain_query_has_no_evidence(
    retriever: Retriever, settings: Settings, query: str, prefix: str
) -> None:
    llm = FakeLLM("never used")
    answer = _service(retriever, settings, llm).answer(query)

    assert answer.status == "no_evidence"
    assert answer.mode == "policy"
    assert answer.text.startswith(prefix)
    assert answer.citations == []
    assert llm.calls == []  # no context, no LLM: nothing to hallucinate from


def test_category_filter_can_remove_all_evidence(retriever: Retriever, settings: Settings) -> None:
    service = _service(retriever, settings)
    assert service.answer("la VPN no conecta").status == "answered"
    assert service.answer("la VPN no conecta", categoria="Accesos").status == "no_evidence"


# --- RN-03 mandatory escalation ------------------------------------------------------


@pytest.mark.parametrize(
    ("query", "language"),
    [
        ("creo que hay un fraude en la cuenta de un cliente", "es"),
        ("alguien entró a mi usuario desde otro equipo", "es"),
        ("la terminal de caja no enciende", "es"),
        ("someone logged into my account from another computer", "en"),
    ],
)
def test_rn03_keywords_escalate_without_steps(
    retriever: Retriever, settings: Settings, query: str, language: str
) -> None:
    llm = FakeLLM("1. do something")
    answer = _service(retriever, settings, llm).answer(query)

    assert answer.status == "mandatory_escalation"
    assert answer.language == language
    assert "1." not in answer.text
    assert "escala" in answer.text.lower()
    assert llm.calls == []


def test_rn03_by_retrieved_article_cites_it(retriever: Retriever, settings: Settings) -> None:
    answer = _service(retriever, settings).answer("la terminal se congela con efectivo")

    assert answer.status == "mandatory_escalation"
    assert answer.mode == "policy"
    assert [c.article_id for c in answer.citations] == ["KB-011"]
    assert "Detén" not in answer.text


def test_rn03_article_in_a_lower_evidence_position_still_escalates(
    settings: Settings, embedder: SpyEmbedder
) -> None:
    # Both articles match; KB-002 ranks first, KB-011 second but above the threshold.
    store = InMemoryVectorStore()
    chunks = [c for c in _chunks() if c.metadata.article_id in {"KB-002", "KB-011"}]
    store.upsert(chunks, embedder.embed_documents([c.text for c in chunks]))
    retriever = Retriever(embedder, store, top_k=3, threshold=0.0)
    query = "usuario bloqueado de Windows con la terminal congelada"
    result = retriever.search(query)
    ids = [a.article_id for a in result.evidence]
    assert "KB-011" in ids and ids[0] != "KB-011"

    llm = FakeLLM("1. Reinicia la terminal.")
    answer = _service(retriever, settings, llm).answer(query)

    assert answer.status == "mandatory_escalation"
    assert [c.article_id for c in answer.citations] == ["KB-011"]
    assert "Reinicia" not in answer.text
    assert llm.calls == []


# --- sensitive data (RF-10, RN-05, HU-05) --------------------------------------------


def test_sensitive_data_is_redacted_everywhere_and_warned(
    retriever: Retriever,
    settings: Settings,
    embedder: SpyEmbedder,
    caplog: pytest.LogCaptureFixture,
) -> None:
    llm = FakeLLM(f"1. Espera 15 minutos.\n\n{SOURCE_ES}")
    query = f"se bloqueó mi usuario de Windows, mi contraseña es {PASSWORD}"
    with caplog.at_level(logging.DEBUG):
        answer = _service(retriever, settings, llm).answer(query)

    assert answer.sensitive_data_warning
    assert answer.text.startswith("Importante: no compartas contraseñas")
    assert answer.status == "answered"
    assert PASSWORD not in answer.text
    assert all(PASSWORD not in q for q in embedder.queries)
    assert "[REDACTED:password]" in embedder.queries[-1]
    (_, user, _) = llm.calls[0]
    assert PASSWORD not in user and "[REDACTED:password]" in user
    assert all(PASSWORD not in str(record.__dict__) for record in caplog.records)


def test_sensitive_warning_also_on_no_evidence(retriever: Retriever, settings: Settings) -> None:
    answer = _service(retriever, settings).answer("pozole recipe, my card is 4111111111111111")
    assert answer.sensitive_data_warning
    assert answer.text.startswith("Important: never share passwords")
    assert answer.status == "no_evidence"


def test_logs_never_contain_the_query_text(
    retriever: Retriever, settings: Settings, caplog: pytest.LogCaptureFixture
) -> None:
    with caplog.at_level(logging.DEBUG):
        _service(retriever, settings).answer("se bloqueó mi usuario de Windows")
    record = next(r for r in caplog.records if r.getMessage() == "Answer produced")
    assert record.status == "answered"  # type: ignore[attr-defined]
    assert record.top_article == "KB-002"  # type: ignore[attr-defined]
    assert all("bloque" not in str(r.__dict__) for r in caplog.records)


# --- with an LLM ---------------------------------------------------------------------


def test_llm_answer_uses_the_template_context_and_timeout(
    retriever: Retriever, settings: Settings
) -> None:
    reply = f"1. Espera 15 minutos.\n2. Usa Desbloquear mi cuenta.\n\n{SOURCE_ES}"
    llm = FakeLLM(reply)
    answer = _service(retriever, settings, llm).answer("se bloqueó mi usuario de Windows")

    assert answer.status == "answered"
    assert answer.mode == "llm"
    assert answer.prompt_key == "answer_with_citation@v1"
    assert answer.text == reply
    assert [c.article_id for c in answer.citations] == ["KB-002"]
    system, user, timeout_s = llm.calls[0]
    assert system == ANSWER_WITH_CITATION.system
    assert timeout_s == settings.llm.timeout_s
    assert '<article id="KB-002"' in user and 'section="pasos"' in user
    assert "1. Espera 15 minutos." in user
    assert "<user_question>\nse bloqueó mi usuario de Windows\n</user_question>" in user


def test_llm_answer_without_citation_gets_the_source_line(
    retriever: Retriever, settings: Settings
) -> None:
    answer = _service(retriever, settings, FakeLLM("1. Espera 15 minutos.")).answer(
        "se bloqueó mi usuario de Windows"
    )
    assert answer.text == f"1. Espera 15 minutos.\n\n{SOURCE_ES}"
    assert [c.article_id for c in answer.citations] == ["KB-002"]


def test_llm_invented_article_id_falls_back_to_extractive(
    retriever: Retriever, settings: Settings, caplog: pytest.LogCaptureFixture
) -> None:
    llm = FakeLLM(f"1. Haz esto.\n\n{SOURCE_ES}\nVer tambien KB-999.")
    with caplog.at_level(logging.WARNING):
        answer = _service(retriever, settings, llm).answer("se bloqueó mi usuario de Windows")

    assert len(llm.calls) == 1
    assert answer.mode == "extractive"
    assert "KB-999" not in answer.text
    assert answer.text.endswith(SOURCE_ES)
    assert [c.article_id for c in answer.citations] == ["KB-002"]
    assert any("outside the evidence" in r.getMessage() for r in caplog.records)


def test_llm_answer_citing_its_source_does_not_get_a_second_source_line(
    retriever: Retriever, settings: Settings
) -> None:
    reply = f"1. Espera 15 minutos.\n\n{SOURCE_ES}"
    answer = _service(retriever, settings, FakeLLM(reply)).answer("se bloqueó mi usuario")
    assert answer.text.count("KB-002") == 1
    assert [c.article_id for c in answer.citations] == ["KB-002"]


def test_llm_output_with_sensitive_data_falls_back_to_extractive(
    retriever: Retriever, settings: Settings
) -> None:
    leaked = "Tu contraseña es Sol2024!xyz, usa tu tarjeta 4111111111111111"
    llm = FakeLLM(f"{leaked}\n\n{SOURCE_ES}")
    answer = _service(retriever, settings, llm).answer("se bloqueó mi usuario de Windows")
    assert answer.mode == "extractive"
    assert "4111111111111111" not in answer.text and "Sol2024" not in answer.text
    assert answer.text.endswith(SOURCE_ES)


def test_llm_saying_no_evidence_becomes_no_evidence(
    retriever: Retriever, settings: Settings
) -> None:
    answer = _service(retriever, settings, FakeLLM(NO_EVIDENCE_TOKEN)).answer(
        "se bloqueó mi usuario de Windows"
    )
    assert answer.status == "no_evidence"
    assert answer.mode == "llm"
    assert answer.citations == []
    assert answer.text.startswith("No lo sé, escalo a un agente humano")


@pytest.mark.parametrize(
    "error", [LLMTimeoutError("fake timed out"), LLMError("fake failed (APIError)")]
)
def test_llm_failure_falls_back_to_extractive_with_a_warning(
    retriever: Retriever,
    settings: Settings,
    caplog: pytest.LogCaptureFixture,
    error: LLMError,
) -> None:
    with caplog.at_level(logging.WARNING):
        answer = _service(retriever, settings, FakeLLM(error=error)).answer(
            "se bloqueó mi usuario de Windows"
        )
    assert answer.status == "answered"
    assert answer.mode == "extractive"
    assert answer.text.endswith(SOURCE_ES)
    warning = next(r for r in caplog.records if "extractive" in r.getMessage())
    assert warning.levelno == logging.WARNING
    assert warning.error == type(error).__name__  # type: ignore[attr-defined]


def test_empty_query_is_rejected(retriever: Retriever, settings: Settings) -> None:
    with pytest.raises(ValueError, match="empty"):
        _service(retriever, settings).answer("   ")


# --- helpers -------------------------------------------------------------------------


def test_format_steps() -> None:
    text = "1. Espera.\n2) Reinicia\n   el equipo.\n- Revisa el cable\n\n* Llama"
    assert format_steps(text) == ["Espera.", "Reinicia el equipo.", "Revisa el cable", "Llama"]
    assert format_steps("Texto suelto\nsigue aquí") == ["Texto suelto sigue aquí"]
    assert format_steps("") == []


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("se bloqueó mi usuario de Windows", "es"),
        ("no puedo entrar a SAP", "es"),
        ("la VPN no conecta", "es"),
        ("my VPN does not connect", "en"),
        ("I forgot my password", "en"),
        ("the printer is not printing", "en"),
        ("Outlook", "es"),
        ("", "es"),
    ],
)
def test_detect_language(text: str, expected: str) -> None:
    assert detect_language(text) == expected


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Sospecho de un FRAUDE", "fraud"),
        ("hay una operación no autorizada", "fraud"),
        ("veo accesos que no reconozco en el core", "unauthorized_access"),
        ("hackearon mi correo", "unauthorized_access"),
        ("my account was compromised", "unauthorized_access"),
        ("el sistema de caja marca error", "cash_system"),
        ("la caja no abre el turno", "cash_system"),
        ("the teller system is down", "cash_system"),
        ("tengo un cargo no reconocido en mi tarjeta", "fraud"),
        ("hay una transacción que no reconozco", "fraud"),
        ("there is an unrecognized charge on my card", "fraud"),
        ("recibí un correo de phishing con mi nombre", "fraud"),
        ("sospecho de robo de identidad de un cliente", "fraud"),
        ("I think this is identity theft", "fraud"),
        ("el cajero automático falla y no entrega efectivo", "cash_system"),
        ("falla en el cajero de la sucursal", "cash_system"),
        ("no abre la caja fuerte de ventanilla", "cash_system"),
        ("the ATM is not working", "cash_system"),
        ("the cash drawer won't open", "cash_system"),
        ("se bloqueó mi usuario de Windows", None),
        ("la impresora no imprime", None),
        ("necesito una caja de clips", None),
        ("el cajero necesita acceso a SAP", None),
        ("necesito una caja de cartón para el equipo", None),
        ("quiero reportar un correo sospechoso de spam", None),
        ("how do I check my card statement in the portal", None),
        ("mi cargo en el sistema de tickets no carga", None),
    ],
)
def test_escalation_reason(text: str, expected: str | None) -> None:
    assert escalation_reason(text) == expected
