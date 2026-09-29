"""Structured logging setup for the API.

Log records are emitted as JSON lines when API_LOG_FORMAT=json (the
default), which is what centralized log tooling (Datadog, ELK, Loki)
expects.  Set API_LOG_FORMAT=text for human-friendly local development.

The request_id populated by middleware.RequestContextMiddleware is
attached to each log record via a contextvar, so logs from anywhere
in the request lifecycle carry the same correlation ID without every
callsite having to pass it around.
"""

from __future__ import annotations

import json
import logging
import sys
from contextvars import ContextVar
from typing import Any

_request_id_var: ContextVar[str | None] = ContextVar("request_id", default=None)


def set_request_id(request_id: str | None) -> None:
    _request_id_var.set(request_id)


def get_request_id() -> str | None:
    return _request_id_var.get()


class _RequestIdFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = _request_id_var.get() or "-"
        return True


class _JSONFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "request_id": getattr(record, "request_id", "-"),
        }
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        # Attach any structured extras that were set on the record.
        for key, value in record.__dict__.items():
            if key in ("args", "asctime", "created", "exc_info", "exc_text", "filename",
                       "funcName", "levelname", "levelno", "lineno", "message", "module",
                       "msecs", "msg", "name", "pathname", "process", "processName",
                       "relativeCreated", "stack_info", "thread", "threadName",
                       "request_id"):
                continue
            payload[key] = value
        return json.dumps(payload, default=str)


def configure_logging(level: str = "INFO", fmt: str = "json") -> None:
    """(Re)configure the root logger for the API process.

    Safe to call multiple times — clears prior handlers first, so the
    lifespan startup can call this without duplicating handlers when
    tests spin up the app repeatedly.
    """
    root = logging.getLogger()
    for h in list(root.handlers):
        root.removeHandler(h)

    handler = logging.StreamHandler(sys.stdout)
    handler.addFilter(_RequestIdFilter())
    if fmt == "json":
        handler.setFormatter(_JSONFormatter())
    else:
        handler.setFormatter(logging.Formatter(
            "%(asctime)s %(levelname)s [%(request_id)s] %(name)s: %(message)s"
        ))

    try:
        root.setLevel(level.upper())
    except (TypeError, ValueError):
        root.setLevel(logging.INFO)
    root.addHandler(handler)
