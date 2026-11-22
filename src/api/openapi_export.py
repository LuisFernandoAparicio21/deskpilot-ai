"""Swagger 2.0 export of the API for the Copilot Studio REST API tool (T19, S8).

Copilot Studio accepts a JSON definition in OpenAPI v2 (Swagger 2.0) only; FastAPI emits
OpenAPI 3.1. ``export_swagger`` builds the real app with placeholder services (nothing is
started, no database or index is opened and no real API key is needed), takes
``app.openapi()`` and converts it by hand:

- ``/health`` is left out (anonymous, it is not a tool of the agent) and the four tools keep
  their ``operationId``;
- ``components.schemas`` -> ``definitions``, ``requestBody`` -> ``in: body`` parameter,
  ``content`` -> ``schema``, ``securitySchemes`` -> ``securityDefinitions`` (apiKey header);
- ``anyOf [X, null]`` -> ``X`` plus ``x-nullable``; ``const`` -> one-value ``enum``;
- summaries, descriptions and examples are rewritten in Spanish so the agent's LLM knows
  when and how to call each tool.

``check_swagger`` then refuses a spec that still has OpenAPI 3 constructs, dangling ``$ref``
or empty descriptions (Copilot Studio blocks blank parameter descriptions).
"""

from __future__ import annotations

import json
import re
from collections.abc import Iterator
from pathlib import Path
from typing import Any, cast

from pydantic import SecretStr

from src.api.app import ApiServices, create_app
from src.utils.config import PROJECT_ROOT, Secrets, Settings

DEFAULT_OUT = PROJECT_ROOT / "integrations" / "copilot_studio" / "openapi.json"
DEFAULT_HOST = "your-deskpilot-host.example.com"
MAX_BYTES = 1_000_000  # custom connector definitions must be under 1 MB
SECURITY_NAME = "api_key"
TOOL_OPERATION_IDS = ("buscar_solucion", "consultar_estado_ticket", "metricas_area", "crear_ticket")

_HOST_RE = re.compile(r"^[A-Za-z0-9]([A-Za-z0-9.-]*[A-Za-z0-9])?(:[0-9]{1,5})?$")
_PLACEHOLDER_KEY = "export-openapi-placeholder-key-not-a-secret"

Json = dict[str, Any]


class ExportError(Exception):
    """The spec cannot be produced or is not valid Swagger 2.0 for Copilot Studio."""


_OPERATIONS: dict[str, tuple[str, str]] = {
    "buscar_solucion": (
        "Buscar solución en la base de conocimiento",
        "Busca en la base de conocimiento de TI de Banco Altiplano la solución a un problema "
        "técnico y la devuelve con citas (id y título del artículo fuente). Úsala SIEMPRE "
        "primero cuando un empleado describa un problema (VPN, contraseña bloqueada, "
        "impresora, correo, caja, etc.), antes de crear un ticket. Envía en `query` el problema "
        "tal como lo dijo el empleado, en español o inglés, sin contraseñas ni PIN. "
        "`categoria` es opcional. Lee `status`: `answered` = respuesta con pasos en `text` y "
        "fuentes en `citations`; `no_evidence` = no hay artículo suficientemente parecido, no "
        "inventes pasos y ofrece crear un ticket; `mandatory_escalation` = caso que exige "
        "escalar a una persona (fraude, acceso no autorizado, sistema de caja caído): muestra "
        "`text` y crea un ticket. Si `sensitive_data_warning` es true, pide al empleado que "
        'no comparta datos sensibles. Ejemplo: {"query": "no puedo conectarme a la VPN"}.',
    ),
    "consultar_estado_ticket": (
        "Consultar el estado de un ticket",
        "Devuelve el estado de un ticket existente a partir de su identificador (por ejemplo "
        "TCK-000123): estado (abierto, en_proceso, resuelto, cerrado), prioridad P1-P4, fechas "
        "y si cumplió o cumple el SLA. Úsala cuando el empleado pregunte cómo va su "
        "solicitud y dé un id de ticket. Si el id no existe responde 404: pide al empleado "
        "que lo verifique, no adivines otro id.",
    ),
    "metricas_area": (
        "Consultar métricas de tickets por área o sucursal",
        "Devuelve métricas de tickets de UN área (por ejemplo Caja) o de UNA sucursal: total "
        "de tickets, cerrados, porcentaje dentro de SLA, horas promedio de resolución y "
        "categorías más frecuentes. Envía exactamente uno de los dos parámetros, `area` o "
        "`sucursal`; con ambos o ninguno responde 422. Úsala para preguntas de líderes como "
        "cómo va el SLA del área Caja. Si no hay tickets con ese nombre responde 404. "
        "Ejemplo: GET /metricas?area=Caja.",
    ),
    "crear_ticket": (
        "Crear un ticket de soporte",
        "Crea un ticket de soporte de TI. La categoría, subcategoría y prioridad (P1-P4) se "
        "clasifican automáticamente y se devuelve el SLA. ACCIÓN QUE ESCRIBE DATOS: úsala "
        "solo cuando buscar_solucion no resolvió el problema (`no_evidence`) o exigió "
        "escalamiento, y después de que el empleado confirme que desea crear el ticket. No la "
        "llames dos veces por el mismo problema. En `descripcion` resume el problema SIN "
        "contraseñas, PIN ni números de tarjeta (si se detectan, se censuran y "
        "`sensitive_data_warning` es true). `escalado` true significa que debe atenderlo una "
        "persona (prioridad P1); informa el `ticket_id` y el SLA al empleado. Ejemplo: "
        '{"descripcion": "La impresora de la caja 2 no imprime comprobantes", '
        '"sucursal": "Sucursal Centro", "area": "Caja", "canal": "Teams"}.',
    ),
}

_ERROR_TEXT: dict[str, str] = {
    "401": "No autorizado: falta la llave X-API-Key o es inválida.",
    "404": "No encontrado.",
    "413": "El cuerpo de la petición es demasiado grande.",
    "422": "Datos de entrada inválidos (longitud, formato o parámetros).",
    "500": "Error interno del servidor.",
    "503": "Servicio no disponible: base de datos o índice de conocimiento.",
    "504": "La petición tardó demasiado (tiempo de espera agotado).",
}
_OK_TEXT: dict[str, str] = {
    "200": "Operación exitosa.",
    "201": "Ticket creado.",
}
_NOT_FOUND: dict[str, str] = {
    "consultar_estado_ticket": "No existe un ticket con ese identificador.",
    "metricas_area": "No hay tickets para esa área o sucursal.",
}

_PARAMETERS: dict[str, str] = {
    "ticket_id": "Identificador del ticket, por ejemplo TCK-000123 (letras, números, - y _).",
    "area": "Nombre del área, por ejemplo Caja. Envía solo uno de area o sucursal.",
    "sucursal": "Nombre de la sucursal, por ejemplo Sucursal Centro. Envía solo uno de "
    "area o sucursal.",
}
_BODY_TEXT: dict[str, str] = {
    "buscar_solucion": "Consulta del empleado y filtro opcional de categoría.",
    "crear_ticket": "Datos del problema, la sucursal y el área del empleado.",
}

# schema -> property -> (description, example)
_Prop = tuple[str, Any]
_PROPERTIES: dict[str, dict[str, _Prop]] = {
    "BuscarSolucionRequest": {
        "query": (
            "Problema descrito por el empleado, en español o inglés, sin contraseñas ni PIN.",
            "no puedo conectarme a la VPN desde mi casa",
        ),
        "categoria": (
            "Filtro opcional por categoría de la base de conocimiento; omítelo si no estás seguro.",
            "Conectividad",
        ),
    },
    "BuscarSolucionResponse": {
        "status": (
            "answered = hay respuesta con citas; no_evidence = no hay artículo suficiente, "
            "ofrece crear un ticket; mandatory_escalation = debe atenderlo una persona.",
            "answered",
        ),
        "language": ("Idioma de la respuesta (es o en).", "es"),
        "text": ("Respuesta lista para mostrar al empleado.", "Reinicia el cliente VPN y ..."),
        "citations": ("Artículos fuente de la respuesta; vacío si no hay evidencia.", None),
        "sensitive_data_warning": (
            "true si la consulta parece contener datos sensibles (contraseñas, PIN, tarjetas).",
            False,
        ),
        "mode": (
            "Cómo se generó el texto: extractive (de los artículos), llm o policy "
            "(mensaje de política).",
            "extractive",
        ),
    },
    "CitationOut": {
        "article_id": ("Identificador del artículo fuente.", "KB-003"),
        "titulo": ("Título del artículo fuente; cítalo al empleado.", "VPN no conecta"),
        "seccion": ("Sección del artículo usada (síntoma, causa, pasos, escalar).", "pasos"),
        "similarity": ("Similitud entre 0 y 1 con la consulta.", 0.61),
    },
    "TicketStatusResponse": {
        "ticket_id": ("Identificador del ticket.", "TCK-000123"),
        "estado": ("Estado actual: abierto, en_proceso, resuelto o cerrado.", "en_proceso"),
        "prioridad": ("Prioridad P1 (crítica) a P4 (baja).", "P2"),
        "fecha_apertura": ("Fecha y hora de apertura.", "2026-11-01T09:30:00"),
        "fecha_cierre": ("Fecha y hora de cierre; nulo si el ticket sigue abierto.", None),
        "sla_horas": ("Horas de SLA según la prioridad.", 8),
        "fecha_limite_sla": ("Fecha y hora límite del SLA.", "2026-11-01T17:30:00"),
        "sla_cumplido": (
            "true si se cerró dentro del SLA, false si no; nulo si sigue abierto.",
            None,
        ),
    },
    "CrearTicketRequest": {
        "descripcion": (
            "Problema descrito por el empleado. Nunca incluyas contraseñas, PIN ni tarjetas.",
            "La impresora de la caja 2 no imprime comprobantes",
        ),
        "sucursal": ("Sucursal del empleado.", "Sucursal Centro"),
        "area": ("Área del empleado.", "Caja"),
        "canal": ("Canal de origen de la solicitud; por defecto Teams.", "Teams"),
    },
    "CrearTicketResponse": {
        "ticket_id": ("Identificador del ticket creado; compártelo con el empleado.", "TCK-005001"),
        "estado": ("Estado inicial, siempre abierto.", "abierto"),
        "categoria": ("Categoría asignada automáticamente.", "Hardware"),
        "subcategoria": ("Subcategoría asignada automáticamente.", "Impresora"),
        "prioridad": ("Prioridad P1 (crítica) a P4 (baja).", "P3"),
        "sla_horas": ("Horas de SLA de la prioridad asignada.", 24),
        "fecha_apertura": ("Fecha y hora de apertura.", "2026-11-21T10:00:00"),
        "fecha_limite_sla": ("Fecha y hora límite del SLA.", "2026-11-22T10:00:00"),
        "escalado": ("true si debe atenderlo una persona (siempre prioridad P1).", False),
        "motivo_escalamiento": (
            "Motivo del escalamiento (fraud, unauthorized_access, cash_system, article); "
            "nulo si no se escaló.",
            None,
        ),
        "sensitive_data_warning": (
            "true si se encontraron datos sensibles y se censuraron antes de guardar.",
            False,
        ),
        "mode": ("Cómo se clasificó: rules (reglas) o llm.", "rules"),
    },
    "CategoryCount": {
        "categoria": ("Nombre de la categoría.", "Accesos"),
        "tickets": ("Cantidad de tickets de esa categoría.", 120),
    },
    "AreaMetricsResponse": {
        "scope": ("Si la métrica es de un área o de una sucursal.", "area"),
        "name": ("Nombre del área o sucursal consultada.", "Caja"),
        "total_tickets": ("Total de tickets.", 450),
        "closed_tickets": ("Tickets cerrados.", 430),
        "sla_cumplido_pct": (
            "Porcentaje de tickets cerrados dentro del SLA; nulo si no hay ninguno cerrado.",
            87.5,
        ),
        "avg_horas_resolucion": ("Horas promedio de resolución; nulo si no hay cerrados.", 14.2),
        "top_categorias": ("Categorías con más tickets, de mayor a menor.", None),
    },
    "ErrorResponse": {
        "code": ("Código de error legible, por ejemplo unauthorized o validation_error.", None),
        "message": ("Mensaje del error.", None),
        "request_id": ("Identificador de la petición, útil para soporte.", None),
        "details": ("Detalle por campo en errores de validación (422).", None),
    },
}
_SCHEMA_TEXT: dict[str, str] = {
    "BuscarSolucionRequest": "Consulta para buscar una solución en la base de conocimiento.",
    "BuscarSolucionResponse": "Respuesta con citas de la base de conocimiento.",
    "CitationOut": "Artículo fuente citado en una respuesta.",
    "TicketStatusResponse": "Estado de un ticket.",
    "CrearTicketRequest": "Datos para crear un ticket de soporte.",
    "CrearTicketResponse": "Ticket creado y clasificado.",
    "CategoryCount": "Cantidad de tickets de una categoría.",
    "AreaMetricsResponse": "Métricas de tickets de un área o sucursal.",
    "ErrorResponse": "Formato uniforme de todos los errores de la API.",
}

_OPENAPI_REF = "#/components/schemas/"
_SWAGGER_REF = "#/definitions/"
_PARAM_KEYS = ("type", "format", "enum", "pattern", "minLength", "maxLength", "default", "items")


def _is_null(node: Json) -> bool:
    return node == {"type": "null"}


def _convert_schema(node: Json) -> Json:
    """OpenAPI 3.1 schema -> Swagger 2.0 schema (recursive)."""
    out: Json = {}
    for key, value in node.items():
        if key in ("title", "anyOf"):
            continue
        if key == "$ref":
            out[key] = str(value).replace(_OPENAPI_REF, _SWAGGER_REF)
        elif key == "const":
            out["enum"] = [value]
        elif key in ("minimum", "maximum") and isinstance(value, float) and value.is_integer():
            out[key] = int(value) if node.get("type") == "integer" else value
        elif key == "properties":
            out[key] = {name: _convert_schema(sub) for name, sub in value.items()}
        elif key in ("items", "additionalProperties") and isinstance(value, dict):
            out[key] = _convert_schema(value)
        else:
            out[key] = value
    if "anyOf" in node:
        variants = [v for v in node["anyOf"] if not _is_null(v)]
        if len(variants) != 1:
            raise ExportError("anyOf with several non-null variants has no Swagger 2.0 form")
        inner = _convert_schema(variants[0])
        if "$ref" in inner:  # siblings of $ref are ignored in Swagger 2.0
            inner = {"allOf": [inner]}
        out = {**inner, **out}
        if len(variants) < len(node["anyOf"]):
            out["x-nullable"] = True
    return out


def _convert_parameter(raw: Json, operation_id: str) -> Json:
    schema = _convert_schema(raw["schema"])
    description = _PARAMETERS.get(raw["name"])
    if description is None:
        raise ExportError(f"{operation_id}: no description for parameter {raw['name']}")
    param: Json = {
        "name": raw["name"],
        "in": raw["in"],
        "required": bool(raw.get("required", False)),
        "description": description,
    }
    for key in _PARAM_KEYS:
        if key in schema:
            param[key] = schema[key]
    if "type" not in param:
        raise ExportError(f"{operation_id}: parameter {raw['name']} has no simple type")
    return param


def _convert_responses(operation_id: str, raw: Json) -> Json:
    responses: Json = {}
    for status, body in sorted(raw.items()):
        out: Json = {}
        if status in _OK_TEXT:
            out["description"] = _OK_TEXT[status]
        elif status == "404":
            out["description"] = _NOT_FOUND.get(operation_id, _ERROR_TEXT["404"])
        else:
            out["description"] = _ERROR_TEXT.get(status, f"Error {status}.")
        content = body.get("content", {}).get("application/json")
        if content is not None:
            out["schema"] = _convert_schema(content["schema"])
        responses[status] = out
    return responses


def _convert_operation(operation_id: str, raw: Json) -> Json:
    if operation_id not in _OPERATIONS:
        raise ExportError(f"operation {operation_id} has no Spanish description")
    summary, description = _OPERATIONS[operation_id]
    parameters = [_convert_parameter(p, operation_id) for p in raw.get("parameters", [])]
    body = raw.get("requestBody")
    operation: Json = {
        "operationId": operation_id,
        "summary": summary,
        "description": description,
    }
    if body is not None:
        operation["consumes"] = ["application/json"]
        parameters.append(
            {
                "name": "body",
                "in": "body",
                "required": bool(body.get("required", False)),
                "description": _BODY_TEXT[operation_id],
                "schema": _convert_schema(body["content"]["application/json"]["schema"]),
            }
        )
    operation["produces"] = ["application/json"]
    operation["parameters"] = parameters
    operation["responses"] = _convert_responses(operation_id, raw["responses"])
    return operation


def _convert_definitions(schemas: Json) -> Json:
    definitions: Json = {}
    for name, raw in schemas.items():
        if name not in _PROPERTIES:
            continue  # e.g. HealthResponse, only used by the left-out /health
        schema = _convert_schema(raw)
        schema["description"] = _SCHEMA_TEXT[name]
        for prop, (description, example) in _PROPERTIES[name].items():
            if prop not in schema["properties"]:
                raise ExportError(f"{name}.{prop} is documented but missing in the schema")
            target = schema["properties"][prop]
            target["description"] = description
            if example is not None:
                target["example"] = example
        definitions[name] = schema
    return definitions


def convert_openapi(spec: Json, host: str) -> Json:
    """Convert FastAPI's OpenAPI 3.x document into a Swagger 2.0 one for Copilot Studio."""
    paths: Json = {}
    for path, methods in spec["paths"].items():
        for method, raw in methods.items():
            operation_id = raw["operationId"]
            if operation_id not in TOOL_OPERATION_IDS:
                continue
            paths.setdefault(path, {})[method] = _convert_operation(operation_id, raw)
    info = spec["info"]
    scheme = next(iter(spec["components"]["securitySchemes"].values()))
    swagger: Json = {
        "swagger": "2.0",
        "info": {
            "title": info["title"],
            "description": (
                "Herramientas del asistente de mesa de servicio de TI de nivel 1 de Banco "
                "Altiplano (banco ficticio, datos sintéticos): buscar soluciones con citas, "
                "consultar tickets, ver métricas y crear tickets."
            ),
            "version": info["version"],
        },
        "host": host,
        "basePath": "/",
        "schemes": ["https"],
        "consumes": ["application/json"],
        "produces": ["application/json"],
        "paths": paths,
        "definitions": _convert_definitions(spec["components"]["schemas"]),
        "securityDefinitions": {
            SECURITY_NAME: {
                "type": "apiKey",
                "in": scheme["in"],
                "name": scheme["name"],
                "description": "Llave de la API (cabecera X-API-Key).",
            }
        },
        "security": [{SECURITY_NAME: []}],
    }
    check_swagger(swagger)
    return swagger


def _walk(node: Any) -> Iterator[Json]:
    if isinstance(node, dict):
        yield node
        for value in node.values():
            yield from _walk(value)
    elif isinstance(node, list):
        for value in node:
            yield from _walk(value)


def check_swagger(spec: Json) -> None:
    """Raise ``ExportError`` if ``spec`` is not usable by Copilot Studio."""
    if spec.get("swagger") != "2.0" or "openapi" in spec:
        raise ExportError("not a Swagger 2.0 document")
    if spec.get("schemes") != ["https"] or not spec.get("host"):
        raise ExportError("host and schemes [https] are required")
    for node in _walk(spec):
        for banned in ("anyOf", "oneOf", "const", "requestBody", "components"):
            if banned in node:
                raise ExportError(f"OpenAPI 3 construct left in the spec: {banned}")
        if node.get("type") == "null":
            raise ExportError("type null is not valid in Swagger 2.0")
        ref = node.get("$ref")
        if ref is not None:
            name = str(ref).removeprefix(_SWAGGER_REF)
            if not str(ref).startswith(_SWAGGER_REF) or name not in spec["definitions"]:
                raise ExportError(f"dangling or invalid $ref: {ref}")
    found: list[str] = []
    for path, methods in spec["paths"].items():
        for method, operation in methods.items():
            found.append(operation["operationId"])
            for field in ("summary", "description"):
                if not operation.get(field):
                    raise ExportError(f"{method} {path}: empty {field}")
            for param in operation.get("parameters", []):
                if not param.get("description"):
                    raise ExportError(f"{operation['operationId']}: empty parameter description")
            for status, response in operation["responses"].items():
                if not response.get("description"):
                    raise ExportError(f"{operation['operationId']}: empty {status} description")
    if sorted(found) != sorted(TOOL_OPERATION_IDS):
        raise ExportError(f"expected operations {TOOL_OPERATION_IDS}, found {found}")
    for name, definition in spec["definitions"].items():
        for prop, value in definition.get("properties", {}).items():
            if not value.get("description"):
                raise ExportError(f"{name}.{prop}: empty description")


def validate_host(host: str) -> str:
    """Bare host name (optionally ``:port``): no scheme, path or spaces."""
    if not _HOST_RE.match(host):
        raise ExportError(
            f"invalid host {host!r}: use only the host name, e.g. api.example.com (no https://)"
        )
    return host


def build_spec_source(settings: Settings) -> Json:
    """``app.openapi()`` of the real app with placeholder services (nothing is started)."""
    safe = settings.model_copy(update={"secrets": Secrets(api_key=SecretStr(_PLACEHOLDER_KEY))})
    placeholder = cast(Any, object())
    services = ApiServices(answers=placeholder, repository=placeholder, index_probe=lambda: None)
    spec: Json = create_app(safe, services).openapi()
    return spec


def export_swagger(settings: Settings, host: str = DEFAULT_HOST) -> Json:
    """The Swagger 2.0 spec for ``host``; raises ``ExportError`` if it is not valid."""
    return convert_openapi(build_spec_source(settings), validate_host(host))


def write_swagger(spec: Json, out: Path) -> int:
    """Write ``spec`` as UTF-8 JSON and return its size in bytes; refuse >= 1 MB."""
    text = json.dumps(spec, indent=2, ensure_ascii=False) + "\n"
    size = len(text.encode("utf-8"))
    if size >= MAX_BYTES:
        raise ExportError(f"spec is {size} bytes; Copilot Studio needs less than 1 MB")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text, encoding="utf-8", newline="\n")
    return size
