"""Swagger 2.0 export for Copilot Studio (T19, S8): real spec, real CLI, no-drift check."""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

import pytest

import main
from src.api.openapi_export import (
    DEFAULT_HOST,
    DEFAULT_OUT,
    MAX_BYTES,
    TOOL_OPERATION_IDS,
    ExportError,
    check_swagger,
    export_swagger,
    validate_host,
    write_swagger,
)
from src.utils.config import Settings, load_settings

Json = dict[str, Any]
EXPECTED_IDS = ["buscar_solucion", "consultar_estado_ticket", "metricas_area", "crear_ticket"]


@pytest.fixture(scope="module")
def settings() -> Settings:
    return load_settings()


@pytest.fixture(scope="module")
def spec(settings: Settings) -> Json:
    return export_swagger(settings)


@pytest.fixture
def fresh(spec: Json) -> Json:
    """A deep copy that a negative test can corrupt."""
    return copy.deepcopy(spec)


def _operations(spec: Json) -> list[tuple[str, str, Json]]:
    return [(p, m, op) for p, methods in spec["paths"].items() for m, op in methods.items()]


def _nodes(node: Any) -> list[Json]:
    found: list[Json] = []
    if isinstance(node, dict):
        found.append(node)
        for value in node.values():
            found.extend(_nodes(value))
    elif isinstance(node, list):
        for value in node:
            found.extend(_nodes(value))
    return found


# ---- shape of the exported document -------------------------------------------------


def test_spec_is_swagger_2_not_openapi_3(spec: Json) -> None:
    assert spec["swagger"] == "2.0"
    assert "openapi" not in spec
    assert "components" not in spec


def test_spec_round_trips_as_json_and_is_under_1_mb(spec: Json) -> None:
    text = json.dumps(spec, ensure_ascii=False)
    assert json.loads(text) == spec
    assert 0 < len(text.encode("utf-8")) < 1_000_000


def test_exactly_the_four_tools_and_no_health(spec: Json) -> None:
    ids = [op["operationId"] for _, _, op in _operations(spec)]
    assert sorted(ids) == sorted(EXPECTED_IDS)
    assert sorted(TOOL_OPERATION_IDS) == sorted(EXPECTED_IDS)
    assert "/health" not in spec["paths"]
    assert "HealthResponse" not in spec["definitions"]


def test_api_key_header_security_applies_to_every_operation(spec: Json) -> None:
    definitions = spec["securityDefinitions"]
    assert len(definitions) == 1
    ((name, scheme),) = definitions.items()
    assert (scheme["type"], scheme["in"], scheme["name"]) == ("apiKey", "header", "X-API-Key")
    assert spec["security"] == [{name: []}]
    for _, _, op in _operations(spec):
        # an operation that overrides security must keep the key; none may opt out
        assert op.get("security", spec["security"]) == [{name: []}]


def test_schemes_https_and_placeholder_host_by_default(spec: Json) -> None:
    assert spec["schemes"] == ["https"]
    assert spec["host"] == DEFAULT_HOST
    assert "example.com" in DEFAULT_HOST


@pytest.mark.parametrize("host", ["api.contoso.com", "deskpilot.example.org:8443"])
def test_host_is_configurable(settings: Settings, host: str) -> None:
    custom = export_swagger(settings, host)
    assert custom["host"] == host
    assert custom["schemes"] == ["https"]


def test_every_operation_has_spanish_summary_and_description(spec: Json) -> None:
    spanish_words = (" el ", " la ", " de ", " un ", " una ", "empleado", "ticket")
    for _, _, op in _operations(spec):
        assert op["summary"].strip()
        assert len(op["description"]) > 80
        lowered = f" {op['description'].lower()} "
        assert sum(word in lowered for word in spanish_words) >= 3, op["operationId"]


def test_every_parameter_and_property_has_a_description(spec: Json) -> None:
    params = 0
    for _, _, op in _operations(spec):
        for param in op["parameters"]:
            params += 1
            assert param["description"].strip()
    assert params >= 5  # ticket_id, area, sucursal and two bodies
    props = 0
    for name, definition in spec["definitions"].items():
        assert definition["description"].strip(), name
        for prop, value in definition["properties"].items():
            props += 1
            assert value["description"].strip(), f"{name}.{prop}"
    assert props > 30


def test_no_openapi3_leftovers_and_no_dangling_refs(spec: Json) -> None:
    refs = 0
    for node in _nodes(spec):
        for banned in ("anyOf", "oneOf", "const", "requestBody", "components", "nullable"):
            assert banned not in node
        assert node.get("type") != "null"
        if "$ref" in node:
            refs += 1
            ref = node["$ref"]
            assert ref.startswith("#/definitions/")
            assert ref.removeprefix("#/definitions/") in spec["definitions"]
    assert refs > 0  # the check is not vacuous


def test_nullable_fields_use_x_nullable(spec: Json) -> None:
    props = spec["definitions"]["TicketStatusResponse"]["properties"]
    assert props["fecha_cierre"]["x-nullable"] is True
    assert props["fecha_cierre"]["type"] == "string"
    assert props["sla_cumplido"]["x-nullable"] is True
    assert props["sla_cumplido"]["type"] == "boolean"
    assert "x-nullable" not in props["estado"]


@pytest.mark.parametrize(
    ("operation_id", "codes"),
    [
        ("buscar_solucion", {"200", "401", "422", "503"}),
        ("consultar_estado_ticket", {"200", "401", "404", "422", "503"}),
        ("metricas_area", {"200", "401", "404", "422", "503"}),
        ("crear_ticket", {"201", "401", "422", "503"}),
    ],
)
def test_error_responses_are_defined(spec: Json, operation_id: str, codes: set[str]) -> None:
    (op,) = [o for _, _, o in _operations(spec) if o["operationId"] == operation_id]
    assert codes <= set(op["responses"])
    for code, response in op["responses"].items():
        assert response["description"].strip(), code
    assert op["responses"]["401"]["schema"] == {"$ref": "#/definitions/ErrorResponse"}


@pytest.mark.xfail(
    strict=True,
    reason=(
        "BUG (src/api/openapi_export.py + app.py): the body-size middleware answers 413 on the "
        "POST tools but no 413 response is declared in the Swagger, so Copilot Studio does not "
        "know it. Remove this xfail when the export declares 413 on POST operations."
    ),
)
@pytest.mark.parametrize("operation_id", ["buscar_solucion", "crear_ticket"])
def test_post_operations_declare_413(spec: Json, operation_id: str) -> None:
    (op,) = [o for _, _, o in _operations(spec) if o["operationId"] == operation_id]
    assert op["responses"]["413"]["description"].strip()


def test_request_bodies_are_body_parameters(spec: Json) -> None:
    for _, method, op in _operations(spec):
        bodies = [p for p in op["parameters"] if p["in"] == "body"]
        assert len(bodies) == (1 if method == "post" else 0)
        for body in bodies:
            assert "$ref" in json.dumps(body["schema"])


# ---- check_swagger negatives ---------------------------------------------------------


def test_check_accepts_the_exported_spec(spec: Json) -> None:
    check_swagger(spec)  # must not raise


def test_check_rejects_untranslated_anyof(fresh: Json) -> None:
    prop = fresh["definitions"]["TicketStatusResponse"]["properties"]["fecha_cierre"]
    prop["anyOf"] = [{"type": "string"}, {"type": "null"}]
    with pytest.raises(ExportError, match="anyOf"):
        check_swagger(fresh)


def test_check_rejects_dangling_ref(fresh: Json) -> None:
    fresh["definitions"]["CitationOut"]["properties"]["titulo"]["$ref"] = "#/definitions/Nope"
    with pytest.raises(ExportError, match="dangling"):
        check_swagger(fresh)


def test_check_rejects_openapi3_style_ref(fresh: Json) -> None:
    fresh["definitions"]["CitationOut"]["properties"]["titulo"]["$ref"] = "#/components/schemas/X"
    with pytest.raises(ExportError, match="ref"):
        check_swagger(fresh)


def test_check_rejects_empty_operation_description(fresh: Json) -> None:
    fresh["paths"]["/metricas"]["get"]["description"] = ""
    with pytest.raises(ExportError, match="empty description"):
        check_swagger(fresh)


def test_check_rejects_empty_parameter_description(fresh: Json) -> None:
    fresh["paths"]["/metricas"]["get"]["parameters"][0]["description"] = ""
    with pytest.raises(ExportError, match="parameter description"):
        check_swagger(fresh)


def test_check_rejects_empty_property_description(fresh: Json) -> None:
    fresh["definitions"]["CitationOut"]["properties"]["titulo"]["description"] = ""
    with pytest.raises(ExportError, match="CitationOut.titulo"):
        check_swagger(fresh)


@pytest.mark.parametrize("bad", [{"swagger": "3.0"}, {"openapi": "3.1.0"}])
def test_check_rejects_wrong_version(fresh: Json, bad: Json) -> None:
    fresh.pop("swagger")
    fresh.update(bad)
    with pytest.raises(ExportError, match="Swagger 2.0"):
        check_swagger(fresh)


def test_check_rejects_missing_host_and_http_scheme(fresh: Json) -> None:
    fresh["host"] = ""
    with pytest.raises(ExportError, match="host"):
        check_swagger(fresh)
    fresh["host"] = "a.example.com"
    fresh["schemes"] = ["http"]
    with pytest.raises(ExportError, match="https"):
        check_swagger(fresh)


def test_check_rejects_a_missing_operation(fresh: Json) -> None:
    del fresh["paths"]["/metricas"]
    with pytest.raises(ExportError, match="expected operations"):
        check_swagger(fresh)


@pytest.mark.parametrize(
    "host",
    ["https://x.com", "https://x.com/a", "x.com/a", "x .com", "", "-x.com", "x.com:", "a_b.com"],
)
def test_validate_host_rejects_urls_paths_and_garbage(host: str) -> None:
    with pytest.raises(ExportError, match="invalid host"):
        validate_host(host)


def test_export_refuses_an_invalid_host(settings: Settings) -> None:
    with pytest.raises(ExportError):
        export_swagger(settings, "https://x.com/a")


def test_write_swagger_refuses_one_megabyte_or_more(spec: Json, tmp_path: Path) -> None:
    big = copy.deepcopy(spec)
    big["info"]["description"] = "x" * MAX_BYTES
    out = tmp_path / "big.json"
    with pytest.raises(ExportError, match="1 MB"):
        write_swagger(big, out)
    assert not out.exists()


def test_write_swagger_writes_utf8_json_and_returns_its_size(spec: Json, tmp_path: Path) -> None:
    out = tmp_path / "nested" / "openapi.json"
    size = write_swagger(spec, out)
    raw = out.read_bytes()
    assert size == len(raw) < MAX_BYTES
    assert b"\r\n" not in raw
    assert raw.endswith(b"\n")
    assert json.loads(raw.decode("utf-8")) == spec
    assert "solución".encode() in raw  # not escaped to ó


# ---- CLI -----------------------------------------------------------------------------


def test_cli_works_without_api_key_and_writes_to_out(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.delenv("DESKPILOT_API_KEY", raising=False)
    out = tmp_path / "o.json"
    assert main.main(["export-openapi", "--out", str(out)]) == main.EXIT_OK
    text = out.read_text(encoding="utf-8")
    written = json.loads(text)
    assert written["swagger"] == "2.0"
    assert written["host"] == DEFAULT_HOST
    stdout = capsys.readouterr().out
    assert "placeholder" in stdout
    assert "export-openapi-placeholder-key" not in stdout + text


def test_cli_custom_host_and_default_file_untouched(tmp_path: Path) -> None:
    before = DEFAULT_OUT.read_bytes()
    out = tmp_path / "o.json"
    assert main.main(["export-openapi", "--host", "api.contoso.com", "--out", str(out)]) == 0
    assert json.loads(out.read_text(encoding="utf-8"))["host"] == "api.contoso.com"
    assert DEFAULT_OUT.read_bytes() == before


def test_cli_rejects_a_url_as_host_with_exit_3(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    out = tmp_path / "o.json"
    code = main.main(["export-openapi", "--host", "https://x.com/a", "--out", str(out)])
    assert code == main.EXIT_DATA_ERROR == 3
    assert not out.exists()
    assert "invalid host" in capsys.readouterr().err


# ---- no drift ------------------------------------------------------------------------


def test_committed_openapi_json_matches_what_the_code_generates_today(
    settings: Settings, tmp_path: Path
) -> None:
    regenerated = tmp_path / "openapi.json"
    write_swagger(export_swagger(settings), regenerated)
    assert DEFAULT_OUT.read_text(encoding="utf-8") == regenerated.read_text(encoding="utf-8"), (
        "integrations/copilot_studio/openapi.json is stale: run `python main.py export-openapi`"
    )


def test_committed_openapi_json_passes_check_swagger() -> None:
    check_swagger(json.loads(DEFAULT_OUT.read_text(encoding="utf-8")))


# ---- optional external validator -----------------------------------------------------


def test_spec_is_valid_per_openapi_spec_validator(spec: Json) -> None:
    validator = pytest.importorskip(
        "openapi_spec_validator", reason="openapi-spec-validator is not installed (optional)"
    )
    validator.validate(copy.deepcopy(spec))
