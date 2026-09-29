"""FastAPI application for the eRTMAC-NWIS geological intelligence system.

Router-based layout:

  api/main.py    is intentionally NOT here — this module IS the app
                 entrypoint (`uvicorn api.app:app`).  This keeps the
                 existing import path (`from api.app import app`) that
                 the integration test suite already uses.
  api/config.py  environment-driven settings, no hard-coded secrets
  api/deps.py    connection pool + graph runner dependencies
  api/errors.py  uniform structured error responses
  api/logging.py structured JSON logging with request-ID context
  api/middleware.py request-ID + timing + access log middleware
  api/routers/   one router per resource group (health, wells, query,
                 events, risk, documents)

Security invariants (do NOT relax):

  * No API keys / DB credentials are hard-coded — all come from env.
  * All SQL uses parameterized placeholders; no LLM ever generates SQL.
  * 5xx error messages returned to the client are generic; details go
    only to server logs so internals never leak.
  * CORS is off by default; enable via API_CORS_ORIGINS env var.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import get_api_settings
from .deps import ConnectionPool
from .errors import register_error_handlers
from .logging import configure_logging
from .middleware import RequestContextMiddleware
from .routers import documents as documents_router
from .routers import events as events_router
from .routers import health as health_router
from .routers import query as query_router
from .routers import risk as risk_router
from .routers import wells as wells_router

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup: open DB pool + LLM-backed graph runner (if configured).
    Shutdown: close the pool.

    Failures here are handled defensively — if the DB isn't reachable
    or Groq isn't configured, the app still comes up and endpoints
    that don't need those resources still serve.  Endpoints that do
    need them raise a clear 503.
    """
    settings = get_api_settings()
    configure_logging(level=settings.log_level, fmt=settings.log_format)

    # DB pool -----------------------------------------------------------
    try:
        app.state.db_pool = ConnectionPool(
            minconn=settings.db_pool_min,
            maxconn=settings.db_pool_max,
            dsn_kwargs=settings.db_config(),
        )
        logger.info("db pool initialised (min=%d max=%d)",
                    settings.db_pool_min, settings.db_pool_max)
    except Exception as exc:
        # Do not raise: some endpoints don't need DB (e.g. /health can
        # still report "unreachable"), and CI may run tests without a
        # local Postgres.
        logger.warning("db pool init failed, will use per-request "
                       "connections instead: %s", exc)
        app.state.db_pool = None

    # LLM graph runner --------------------------------------------------
    app.state.graph_runner = None
    if settings.llm_enabled and settings.groq_api_key:
        try:
            from graph.workflow import QueryGraphRunner

            app.state.graph_runner = QueryGraphRunner(use_llm=True)
            logger.info("QueryGraphRunner initialised (LLM enabled)")
        except Exception as exc:
            logger.warning("QueryGraphRunner init failed: %s", exc)
            app.state.graph_runner = None
    else:
        logger.info("LLM disabled (no GROQ_API_KEY) — /query endpoint "
                    "returns 503; /query/structured still works")

    try:
        yield
    finally:
        pool = getattr(app.state, "db_pool", None)
        if pool is not None:
            pool.closeall()
            # Set to None so a subsequent app run (e.g. sequential
            # TestClients in the test suite) doesn't try to reuse the
            # closed pool.  A fresh pool is opened on the next
            # lifespan startup.
            app.state.db_pool = None
            logger.info("db pool closed")


app = FastAPI(
    title="eRTMAC-NWIS Geological Intelligence API",
    version="0.2.0",
    description=(
        "Nearby-well intelligence, geological similarity, historical "
        "drilling event correlation, evidence-based risk assessment, "
        "and document retrieval for the Norwegian Continental Shelf."
    ),
    lifespan=lifespan,
)

# Middleware --------------------------------------------------------
app.add_middleware(RequestContextMiddleware)

# CORS is off by default; only enable if origins are explicitly configured.
_settings = get_api_settings()
if _settings.cors_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=_settings.cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
        expose_headers=["X-Request-ID", "X-Elapsed-Ms"],
    )

# Error handlers ----------------------------------------------------
register_error_handlers(app)

# Routers -----------------------------------------------------------
app.include_router(health_router.router)
app.include_router(wells_router.router)
app.include_router(query_router.router)
app.include_router(events_router.router)
app.include_router(risk_router.router)
app.include_router(documents_router.router)
