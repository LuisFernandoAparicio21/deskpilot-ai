"""Request and response models of the API (S8, RF-17, RF-19, RNF-04, RNF-06).

Every request model forbids unknown fields and trims strings. The length limit of the
search query comes from ``api.max_query_chars``, so ``build_search_request`` creates the
model for the configured limit; responses never echo the input back.
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import Annotated, Literal, get_args

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, create_model
from pydantic.functional_validators import AfterValidator

from src.ingestion.ticket_generator import CANALES
from src.retrieval.answer_service import KNOWN_CATEGORIES, AnswerMode, AnswerStatus

Categoria = Literal["Accesos", "Comunicaciones", "Conectividad", "Hardware", "Software", "General"]
if set(get_args(Categoria)) != set(KNOWN_CATEGORIES):  # keep the OpenAPI enum in sync
    raise RuntimeError("Categoria does not match the knowledge base categories")

Canal = Literal["portal", "correo", "teléfono", "Teams"]
if set(get_args(Canal)) != set(CANALES):  # keep the OpenAPI enum in sync with the dataset
    raise RuntimeError("Canal does not match the ticket channels")

TICKET_ID_PATTERN = r"^[A-Za-z0-9_-]{1,32}$"
AREA_MAX_CHARS = 64
_CONTROL_CHARS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
# Letters (with accents), digits, spaces and a few separators: area and sucursal names.
_NAME = re.compile(r"^[\w .,&/()-]+$")


def _no_control_chars(value: str) -> str:
    if _CONTROL_CHARS.search(value):
        raise ValueError("control characters are not allowed")
    return value


def _is_name(value: str) -> str:
    if not _NAME.match(value):
        raise ValueError("only letters, digits, spaces and . , & / ( ) - are allowed")
    return value


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class BuscarSolucionRequest(_Strict):
    """Input of ``buscar_solucion``; ``build_search_request`` sets the configured max length."""

    query: Annotated[
        str,
        StringConstraints(min_length=1),
        AfterValidator(_no_control_chars),
        Field(description="Problem described by the employee, in Spanish or English."),
    ]
    categoria: Categoria | None = Field(
        default=None, description="Optional filter by knowledge base category."
    )


def build_search_request(max_chars: int) -> type[BuscarSolucionRequest]:
    """``BuscarSolucionRequest`` with ``query`` limited to ``max_chars`` characters."""
    model: type[BuscarSolucionRequest] = create_model(
        "BuscarSolucionRequest",
        __base__=BuscarSolucionRequest,
        query=(
            Annotated[
                str,
                StringConstraints(min_length=1, max_length=max_chars),
                AfterValidator(_no_control_chars),
            ],
            Field(description="Problem described by the employee, in Spanish or English."),
        ),
    )
    return model


class CitationOut(BaseModel):
    article_id: str
    titulo: str
    seccion: str
    similarity: float = Field(ge=0.0, le=1.0)


class BuscarSolucionResponse(BaseModel):
    """Cited answer; ``text`` is ready to show to the user (RN-04)."""

    status: AnswerStatus
    language: Literal["es", "en"]
    text: str
    citations: list[CitationOut]
    sensitive_data_warning: bool
    mode: AnswerMode


class TicketStatusResponse(BaseModel):
    """Status of a ticket (RF-17); only these fields are ever exposed."""

    ticket_id: str
    estado: Literal["abierto", "en_proceso", "resuelto", "cerrado"]
    prioridad: Literal["P1", "P2", "P3", "P4"]
    fecha_apertura: datetime
    fecha_cierre: datetime | None
    sla_horas: int
    fecha_limite_sla: datetime
    sla_cumplido: bool | None


AreaName = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=AREA_MAX_CHARS),
    AfterValidator(_is_name),
]


class CrearTicketRequest(_Strict):
    """Input of ``crear_ticket``; ``build_create_request`` sets the configured max length."""

    descripcion: Annotated[
        str,
        StringConstraints(min_length=5),
        AfterValidator(_no_control_chars),
        Field(description="Problem described by the employee. Never include passwords or PINs."),
    ]
    sucursal: AreaName = Field(description="Branch of the employee.")
    area: AreaName = Field(description="Area of the employee.")
    canal: Canal = Field(default="Teams", description="Channel the request came from.")


def build_create_request(max_chars: int) -> type[CrearTicketRequest]:
    """``CrearTicketRequest`` with ``descripcion`` limited to ``max_chars`` characters."""
    model: type[CrearTicketRequest] = create_model(
        "CrearTicketRequest",
        __base__=CrearTicketRequest,
        descripcion=(
            Annotated[
                str,
                StringConstraints(min_length=5, max_length=max_chars),
                AfterValidator(_no_control_chars),
            ],
            Field(
                description="Problem described by the employee. Never include passwords or PINs."
            ),
        ),
    )
    return model


class CrearTicketResponse(BaseModel):
    """The created ticket (RF-16); never echoes the description."""

    ticket_id: str
    estado: Literal["abierto"]
    categoria: str
    subcategoria: str
    prioridad: Literal["P1", "P2", "P3", "P4"]
    sla_horas: int
    fecha_apertura: datetime
    fecha_limite_sla: datetime
    escalado: bool = Field(description="True when RN-03 requires a human (always P1).")
    motivo_escalamiento: Literal["fraud", "unauthorized_access", "cash_system", "article"] | None
    sensitive_data_warning: bool = Field(
        description="True when sensitive data was found and redacted before saving (RN-05)."
    )
    mode: Literal["rules", "llm"]


class CategoryCount(BaseModel):
    categoria: str
    tickets: int = Field(ge=0)


class AreaMetricsResponse(BaseModel):
    """Metrics of one area or branch (RF-19)."""

    scope: Literal["area", "sucursal"]
    name: str
    total_tickets: int = Field(ge=0)
    closed_tickets: int = Field(ge=0)
    sla_cumplido_pct: float | None = Field(
        description="Percent of closed tickets inside SLA; null when none is closed."
    )
    avg_horas_resolucion: float | None
    top_categorias: list[CategoryCount]


class ComponentHealth(BaseModel):
    status: Literal["ok", "unavailable"]


class HealthResponse(BaseModel):
    """Overall state of the API; anonymous callers get no internals (RF-26)."""

    status: Literal["ok", "degraded"]


class ErrorResponse(BaseModel):
    """Uniform error body (RNF-06)."""

    code: str
    message: str
    request_id: str | None
    details: list[dict[str, str]] | None = None
