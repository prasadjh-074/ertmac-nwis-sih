"""Shared FastAPI dependencies: connection pool + graph runner.

`get_conn` yields a pooled psycopg2 connection and returns it to the
pool afterwards even if the handler raises.  Endpoints that call into
nearby/, retrieval/, events/, risk/ should pass this connection
through so the whole pipeline uses one pooled connection per request
instead of opening a new socket per call.

Nothing in this module holds mutable per-request state; everything
lives on the FastAPI app.state, which is set up in main.py's lifespan.
"""

from __future__ import annotations

import logging
from contextlib import contextmanager
from typing import Iterator, Optional

from fastapi import Request

from .config import get_api_settings

logger = logging.getLogger(__name__)


class ConnectionPool:
    """Thin wrapper around psycopg2.pool.SimpleConnectionPool.

    Kept as a plain class (not a global) so tests can substitute a
    fake pool via FastAPI's dependency_overrides without patching
    module globals.
    """

    def __init__(self, minconn: int, maxconn: int, dsn_kwargs: dict):
        # Import here to keep psycopg2 out of import-time side effects
        # for tests that don't need the DB at all.
        from psycopg2.pool import SimpleConnectionPool

        self._pool = SimpleConnectionPool(minconn=minconn, maxconn=maxconn, **dsn_kwargs)

    def getconn(self):
        return self._pool.getconn()

    def putconn(self, conn, close: bool = False) -> None:
        try:
            self._pool.putconn(conn, close=close)
        except Exception as exc:  # pragma: no cover — pool bookkeeping is defensive
            logger.warning("putconn failed: %s", exc)

    def closeall(self) -> None:
        try:
            self._pool.closeall()
        except Exception:  # pragma: no cover
            pass

    @contextmanager
    def connection(self) -> Iterator:
        conn = self.getconn()
        try:
            yield conn
            if not conn.closed:
                conn.commit()
        except Exception:
            if not conn.closed:
                try:
                    conn.rollback()
                except Exception:
                    pass
            raise
        finally:
            self.putconn(conn)


def get_conn(request: Request) -> Iterator:
    """FastAPI dependency: yield a pooled connection, return it afterward.

    If the app has no pool (e.g. lifespan didn't open one because the
    test disabled the DB), a fresh single-shot connection is returned
    instead so the endpoint can still function — matching the pre-pool
    behavior of the original api/app.py.
    """
    pool: Optional[ConnectionPool] = getattr(request.app.state, "db_pool", None)
    if pool is None:
        import psycopg2

        settings = get_api_settings()
        conn = psycopg2.connect(**settings.db_config())
        try:
            yield conn
        finally:
            try:
                conn.close()
            except Exception:
                pass
        return

    with pool.connection() as conn:
        yield conn


def get_graph_runner(request: Request):
    """FastAPI dependency: return the shared QueryGraphRunner, or None
    if LLM support isn't configured (no GROQ_API_KEY in this env).

    Endpoints that require the runner should raise 503 when it's None.
    """
    return getattr(request.app.state, "graph_runner", None)
