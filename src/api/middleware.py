"""Request context middleware: request_id, body limit, safe headers, access log (S8, S17).

A pure ASGI middleware (not ``BaseHTTPMiddleware``) so that the ``X-Request-ID`` header
is on every response, including 500 errors it builds itself. The request id is the
client's ``X-Request-ID`` when it looks safe, otherwise a new one; it is stored in the
logging ``ContextVar`` so every log line of the request carries it.

The access log has the method, the route path, the status and the duration. It never
logs headers, the query string or the body (API key, personal data).
"""

from __future__ import annotations

import logging
import re
import time

from starlette.datastructures import Headers, MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from src.api.errors import error_response
from src.utils.logging import new_request_id, request_context

logger = logging.getLogger(__name__)

REQUEST_ID_HEADER = "X-Request-ID"
_SAFE_REQUEST_ID = re.compile(r"^[A-Za-z0-9._-]{8,64}$")
_SECURITY_HEADERS = {
    "cache-control": "no-store",
    "x-content-type-options": "nosniff",
}


class BodyTooLargeError(Exception):
    """The request body is bigger than ``max_body_bytes``."""


class RequestContextMiddleware:
    def __init__(self, app: ASGIApp, *, max_body_bytes: int) -> None:
        self.app = app
        self._max_body_bytes = max_body_bytes

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        incoming = Headers(scope=scope).get(REQUEST_ID_HEADER, "")
        request_id = incoming if _SAFE_REQUEST_ID.match(incoming) else new_request_id()
        with request_context(request_id):
            await self._handle(scope, receive, send, request_id)

    async def _handle(self, scope: Scope, receive: Receive, send: Send, request_id: str) -> None:
        started = time.perf_counter()
        status = 500
        response_started = False

        async def send_wrapper(message: Message) -> None:
            nonlocal status, response_started
            if message["type"] == "http.response.start":
                response_started = True
                status = message["status"]
                headers = MutableHeaders(scope=message)
                headers[REQUEST_ID_HEADER] = request_id
                for name, value in _SECURITY_HEADERS.items():
                    headers.setdefault(name, value)
            await send(message)

        received = 0

        async def receive_wrapper() -> Message:
            nonlocal received
            message = await receive()
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                if received > self._max_body_bytes:
                    raise BodyTooLargeError
            return message

        declared = Headers(scope=scope).get("content-length", "")
        try:
            if declared.isdigit() and int(declared) > self._max_body_bytes:
                raise BodyTooLargeError
            await self.app(scope, receive_wrapper, send_wrapper)
        except BodyTooLargeError:
            if not response_started:
                response = error_response(413, "payload_too_large", "Request body too large.")
                await response(scope, receive, send_wrapper)
        except Exception as exc:
            # Type only: the text of an unexpected error may contain user input.
            logger.error("Unhandled error", extra={"error": type(exc).__name__})
            if not response_started:
                response = error_response(500, "internal_error", "Internal server error.")
                await response(scope, receive, send_wrapper)
        finally:
            route = scope.get("route")
            logger.info(
                "Request handled",
                extra={
                    "method": scope.get("method"),
                    "path": getattr(route, "path", None) or "unmatched",
                    "status": status,
                    "duration_ms": round((time.perf_counter() - started) * 1000, 1),
                },
            )
