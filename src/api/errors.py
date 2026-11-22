"""One error format for the whole API (RNF-06, S8).

Every error is ``{"code", "message", "request_id", "details"}``. Messages are fixed
texts: they never include the request input, exception text, paths or secrets.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from src.utils.logging import get_request_id

logger = logging.getLogger(__name__)

_STATUS_CODES = {
    400: "bad_request",
    401: "unauthorized",
    404: "not_found",
    405: "method_not_allowed",
    413: "payload_too_large",
    422: "validation_error",
    500: "internal_error",
    503: "service_unavailable",
    504: "timeout",
}
_STATUS_MESSAGES = {
    400: "Bad request.",
    401: "Missing or invalid API key.",
    404: "Resource not found.",
    405: "Method not allowed.",
    413: "Request body too large.",
    422: "The request is not valid.",
    500: "Internal server error.",
    503: "A required service is unavailable.",
    504: "The request took too long.",
}


def status_code_name(status_code: int) -> str:
    return _STATUS_CODES.get(status_code, "error")


def status_message(status_code: int) -> str:
    return _STATUS_MESSAGES.get(status_code, "Request failed.")


class ApiError(Exception):
    """Raise from a route to answer with the uniform error body."""

    def __init__(
        self,
        status_code: int,
        code: str | None = None,
        message: str | None = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        self.status_code = status_code
        self.code = code or status_code_name(status_code)
        self.message = message or status_message(status_code)
        self.headers = headers
        super().__init__(self.code)


def error_response(
    status_code: int,
    code: str,
    message: str,
    *,
    details: list[dict[str, str]] | None = None,
    headers: dict[str, str] | None = None,
) -> JSONResponse:
    """The uniform body, with the request_id of the current request."""
    body: dict[str, object] = {
        "code": code,
        "message": message,
        "request_id": get_request_id(),
        "details": details,
    }
    return JSONResponse(body, status_code=status_code, headers=headers)


async def _api_error(_request: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, ApiError)
    return error_response(exc.status_code, exc.code, exc.message, headers=exc.headers)


async def _http_error(_request: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, StarletteHTTPException)
    status = exc.status_code
    return error_response(
        status,
        status_code_name(status),
        status_message(status),
        headers=dict(exc.headers) if exc.headers else None,
    )


def _safe_field(err: Any) -> str:
    """Field path for a 422 detail; never echo client-chosen names (extra_forbidden)."""
    if err["type"] == "extra_forbidden":
        return "body"
    return ".".join(str(part) for part in err["loc"])


async def _validation_error(_request: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, RequestValidationError)
    details = [{"field": _safe_field(err), "issue": str(err["type"])} for err in exc.errors()]
    logger.info("Request rejected by validation", extra={"errors": len(details)})
    return error_response(422, "validation_error", status_message(422), details=details)


def install_error_handlers(app: FastAPI) -> None:
    """Register the handlers; unexpected exceptions are caught by the request middleware."""
    app.add_exception_handler(ApiError, _api_error)
    app.add_exception_handler(StarletteHTTPException, _http_error)
    app.add_exception_handler(RequestValidationError, _validation_error)
