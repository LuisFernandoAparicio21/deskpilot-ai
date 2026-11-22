"""Strict input validation of the API (RNF-04, S8): limits, enums, control chars, injection."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import get_args

import pytest
from fastapi.testclient import TestClient

from src.api.schemas import AREA_MAX_CHARS, Categoria
from src.retrieval.answer_service import KNOWN_CATEGORIES
from tests.unit.conftest import KEY_HEADER, Env, settings_with_key


def _search(client: TestClient, body: object) -> int:
    return client.post("/buscar_solucion", json=body, headers=KEY_HEADER).status_code


def test_query_length_limit_comes_from_config(client: TestClient, env: Env) -> None:
    limit = env.settings.api.max_query_chars
    assert _search(client, {"query": "a" * limit}) == 200
    assert _search(client, {"query": "a" * (limit + 1)}) == 422


def test_query_limit_follows_a_different_config(
    tmp_path: Path, make_client: Callable[[Env], TestClient]
) -> None:
    small = Env(settings_with_key(tmp_path, max_query_chars=10))
    client = make_client(small)
    assert _search(client, {"query": "a" * 10}) == 200
    assert _search(client, {"query": "a" * 11}) == 422


@pytest.mark.parametrize("query", ["", "   ", "\t\n "])
def test_empty_or_blank_query_is_422(client: TestClient, env: Env, query: str) -> None:
    assert _search(client, {"query": query}) == 422
    assert env.search.calls == []


def test_query_is_trimmed_before_it_reaches_the_service(client: TestClient, env: Env) -> None:
    assert _search(client, {"query": "  no abre la VPN \n"}) == 200
    assert env.search.calls == [("no abre la VPN", None)]


@pytest.mark.parametrize("char", ["\x00", "\x01", "\x07", "\x08", "\x0b", "\x0c", "\x1b", "\x7f"])
def test_control_characters_in_query_are_422(client: TestClient, env: Env, char: str) -> None:
    assert _search(client, {"query": f"hola{char}mundo"}) == 422
    assert env.search.calls == []


def test_newline_tab_and_unicode_are_allowed_inside_a_query(client: TestClient, env: Env) -> None:
    query = "Línea 1\n\tLínea 2: ¿cómo reseteo mi contraseña? 日本語"
    assert _search(client, {"query": query}) == 200
    assert env.search.calls == [(query, None)]


@pytest.mark.parametrize("value", [None, 5, ["a"], {"a": 1}, True])
def test_query_must_be_a_string(client: TestClient, value: object) -> None:
    assert _search(client, {"query": value}) == 422


def test_query_is_required(client: TestClient) -> None:
    assert _search(client, {}) == 422
    assert _search(client, {"categoria": "Accesos"}) == 422


@pytest.mark.parametrize(
    "body", [{"query": "x", "extra": 1}, {"query": "x", "categoria": None, "k": 3}]
)
def test_extra_fields_are_forbidden(client: TestClient, env: Env, body: dict[str, object]) -> None:
    response = client.post("/buscar_solucion", json=body, headers=KEY_HEADER)
    assert response.status_code == 422
    assert any(d["issue"] == "extra_forbidden" for d in response.json()["details"])
    assert env.search.calls == []


@pytest.mark.parametrize("body", [[], "text", 5, None])
def test_body_must_be_a_json_object(client: TestClient, body: object) -> None:
    assert _search(client, body) == 422


def test_malformed_json_is_422_with_uniform_body(client: TestClient) -> None:
    response = client.post(
        "/buscar_solucion",
        content=b'{"query": ',
        headers={**KEY_HEADER, "Content-Type": "application/json"},
    )
    assert response.status_code == 422
    assert response.json()["code"] == "validation_error"


@pytest.mark.parametrize("categoria", sorted(KNOWN_CATEGORIES))
def test_every_known_category_is_accepted_and_forwarded(
    client: TestClient, env: Env, categoria: str
) -> None:
    assert _search(client, {"query": "x", "categoria": categoria}) == 200
    assert env.search.calls[-1] == ("x", categoria)


@pytest.mark.parametrize(
    "categoria", ["Invalida", "accesos", "ACCESOS", " Accesos", "Accesos ", "", "x' OR '1'='1", 3]
)
def test_unknown_category_is_422(client: TestClient, env: Env, categoria: object) -> None:
    assert _search(client, {"query": "x", "categoria": categoria}) == 422
    assert env.search.calls == []


def test_categoria_literal_matches_knowledge_base_categories() -> None:
    assert set(get_args(Categoria)) == set(KNOWN_CATEGORIES)


def test_openapi_enum_of_categoria_matches_knowledge_base_categories(client: TestClient) -> None:
    schema = client.app.openapi()  # type: ignore[attr-defined]
    properties = schema["components"]["schemas"]["BuscarSolucionRequest"]["properties"]
    enum = next(o["enum"] for o in properties["categoria"]["anyOf"] if "enum" in o)
    assert set(enum) == set(KNOWN_CATEGORIES)
    assert properties["query"]["maxLength"] == 500


@pytest.mark.parametrize(
    "ticket_id",
    ["bad%20id", "a" * 33, "TCK%27%3BDROP", "TCK-1%00", "TCK%0A1", "%C3%A1", "TCK.1"],
)
def test_invalid_ticket_id_is_422(client: TestClient, env: Env, ticket_id: str) -> None:
    response = client.get(f"/tickets/{ticket_id}", headers=KEY_HEADER)
    assert response.status_code == 422
    assert response.json()["code"] == "validation_error"
    assert env.repo.ticket_calls == []


def test_path_traversal_in_ticket_id_never_reaches_the_repository(
    client: TestClient, env: Env
) -> None:
    """%2F is decoded to a slash, so the path matches no route: uniform 404, no query."""
    response = client.get("/tickets/..%2Fetc", headers=KEY_HEADER)
    assert response.status_code == 404
    assert set(response.json()) == {"code", "message", "request_id", "details"}
    assert env.repo.ticket_calls == []


@pytest.mark.parametrize("ticket_id", ["TCK-000001", "a", "a" * 32, "A_b-9"])
def test_valid_ticket_ids_reach_the_repository(
    client: TestClient, env: Env, ticket_id: str
) -> None:
    assert client.get(f"/tickets/{ticket_id}", headers=KEY_HEADER).status_code in (200, 404)
    assert env.repo.ticket_calls == [ticket_id]


def test_ticket_id_422_does_not_echo_the_input(client: TestClient) -> None:
    response = client.get("/tickets/ZZZ%20SECRETMARK", headers=KEY_HEADER)
    assert response.status_code == 422
    assert "SECRETMARK" not in response.text


@pytest.mark.parametrize(
    "params", ["", "area=", "area=%20%20", "sucursal=", "area=Caja&sucursal=Caja"]
)
def test_area_or_sucursal_missing_empty_or_both_is_422(
    client: TestClient, env: Env, params: str
) -> None:
    response = client.get(f"/metricas?{params}", headers=KEY_HEADER)
    assert response.status_code == 422
    assert response.json()["code"] == "validation_error"
    assert env.repo.metric_calls == []


@pytest.mark.parametrize("param", ["area", "sucursal"])
@pytest.mark.parametrize(
    "value",
    [
        "x' OR '1'='1",
        "Caja'; DROP TABLE tickets;--",
        'Caja" OR 1=1',
        "Caja\x00",
        "Ca\nja",
        "Caja\x1b[31m",
        "<script>alert(1)</script>",
        "Caja%",
        "Caja;",
        "a" * (AREA_MAX_CHARS + 1),
    ],
)
def test_injection_and_abuse_in_area_or_sucursal_is_422(
    client: TestClient, env: Env, param: str, value: str
) -> None:
    response = client.get("/metricas", params={param: value}, headers=KEY_HEADER)
    assert response.status_code == 422
    assert env.repo.metric_calls == []


@pytest.mark.parametrize(
    "value",
    [
        "Caja",
        "a" * AREA_MAX_CHARS,
        "Sinaloa (Centro) 01",
        "Atención & Soporte",
        "Ñandú/Sur",
        "  Caja  ",
    ],
)
def test_legitimate_names_are_accepted_and_trimmed(
    client: TestClient, env: Env, value: str
) -> None:
    response = client.get("/metricas", params={"area": value}, headers=KEY_HEADER)
    assert response.status_code in (200, 404)
    assert env.repo.metric_calls == [("area", value.strip())]


def test_sucursal_scope_is_forwarded(client: TestClient, env: Env) -> None:
    response = client.get("/metricas", params={"sucursal": "Caja"}, headers=KEY_HEADER)
    assert response.status_code == 200
    assert response.json()["scope"] == "sucursal"
    assert env.repo.metric_calls == [("sucursal", "Caja")]
