"""Structured error responses.

Every error the API returns has the same JSON shape:

    {
      "error": {
        "type":      "<short slug e.g. not_found, validation_error>",
        "message":   "<short human message>",
        "status":    <int http status>,
        "request_id":"<X-Request-ID for this request>",
        "detail":    <optional structured detail>
      }
    }

Client applications can rely on this uniform shape.  Internal
exception messages are never leaked verbatim for 5xx responses (that
message goes to server logs); the client gets a generic
"internal_server_error" instead.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)


def _envelope(
    error_type: str,
    message: str,
    http_status: int,
    request_id: str | None,
    detail: Any = None,
) -> dict:
    body: dict = {
        "error": {
            "type": error_type,
            "message": message,
            "status": http_status,
            "request_id": request_id,
        }
    }
    if detail is not None:
        body["error"]["detail"] = detail
    return body


def _slug_for_status(code: int) -> str:
    return {
        400: "bad_request",
        401: "unauthorized",
        403: "forbidden",
        404: "not_found",
        409: "conflict",
        422: "validation_error",
        429: "too_many_requests",
        500: "internal_server_error",
        503: "service_unavailable",
    }.get(code, "error")


def _request_id(request: Request) -> str | None:
    return getattr(request.state, "request_id", None)


async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    slug = _slug_for_status(exc.status_code)
    message = exc.detail if isinstance(exc.detail, str) else slug.replace("_", " ")
    detail = None if isinstance(exc.detail, str) else exc.detail
    return JSONResponse(
        status_code=exc.status_code,
        content=_envelope(slug, str(message), exc.status_code, _request_id(request), detail),
        headers=exc.headers or None,
    )


async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content=_envelope(
            "validation_error",
            "Request validation failed.",
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            _request_id(request),
            detail=exc.errors(),
        ),
    )


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    # Full traceback goes to server logs — client only gets a generic
    # message so internal details / stack frames never leak.
    logger.exception(
        "unhandled error handling %s %s: %s",
        request.method, request.url.path, exc,
    )
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=_envelope(
            "internal_server_error",
            "An internal error occurred.",
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            _request_id(request),
        ),
    )


def register_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(HTTPException, http_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(Exception, unhandled_exception_handler)
