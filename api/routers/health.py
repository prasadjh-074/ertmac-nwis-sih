"""GET /health — liveness + database reachability."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends

from ..deps import get_conn
from ..schemas import HealthResponse

logger = logging.getLogger(__name__)
router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
def health(conn=Depends(get_conn)):
    db_status = "connected"
    try:
        cur = conn.cursor()
        cur.execute("SELECT 1")
        cur.fetchone()
    except Exception as exc:  # pragma: no cover — DB reachability path
        logger.warning("health check DB probe failed: %s", exc)
        db_status = "unreachable"
    return HealthResponse(status="ok", version="0.2.0", database=db_status)
