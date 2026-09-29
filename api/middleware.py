"""HTTP middleware.

RequestContextMiddleware:
- Generates (or forwards) an X-Request-ID for each request and
  binds it to the logging contextvar so every log line inside the
  handler carries it.
- Measures wall-clock handler time and returns it as X-Elapsed-Ms.
- Emits a single access log line per request.

CORS is added by main.py itself, not here, because it needs the
settings object to configure allowed origins.
"""

from __future__ import annotations

import logging
import time
import uuid

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from .logging import set_request_id

logger = logging.getLogger("api.access")

_REQUEST_ID_HEADER = "X-Request-ID"
_ELAPSED_HEADER = "X-Elapsed-Ms"


class RequestContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        request_id = request.headers.get(_REQUEST_ID_HEADER) or uuid.uuid4().hex
        set_request_id(request_id)
        request.state.request_id = request_id

        start = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            elapsed_ms = (time.perf_counter() - start) * 1000
            logger.exception(
                "unhandled exception",
                extra={
                    "path": request.url.path,
                    "method": request.method,
                    "elapsed_ms": round(elapsed_ms, 2),
                },
            )
            set_request_id(None)
            raise

        elapsed_ms = (time.perf_counter() - start) * 1000
        response.headers[_REQUEST_ID_HEADER] = request_id
        response.headers[_ELAPSED_HEADER] = f"{elapsed_ms:.2f}"

        logger.info(
            "request",
            extra={
                "path": request.url.path,
                "method": request.method,
                "status": response.status_code,
                "elapsed_ms": round(elapsed_ms, 2),
            },
        )
        set_request_id(None)
        return response
