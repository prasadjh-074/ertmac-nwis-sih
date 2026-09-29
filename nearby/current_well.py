"""Current well state resolution.

Constructs a CurrentWellState snapshot from the SODIR knowledge graph
(real data) or from a caller-supplied simulation dict (for demos).
Missing fields remain None — never fabricated.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Optional

from .models import CurrentWellState
from .search import _get_connection, get_well_location


def resolve_current_well(
    well_id: str,
    dataset: str,
    conn=None,
) -> Optional[CurrentWellState]:
    """Build a CurrentWellState from real database records.

    Returns None if the well is not found in the identity bridge.
    """
    own_conn = conn is None
    if own_conn:
        conn = _get_connection()
    try:
        loc = get_well_location(well_id, dataset, conn=conn)
        if loc is None:
            return None

        cur = conn.cursor()
        total_depth = None
        status = None
        operator = None

        if loc.sodir_wellbore_id is not None:
            cur.execute(
                """
                SELECT total_depth_m, status, operator
                FROM core.wellbore
                WHERE wellbore_id = %s
                """,
                (loc.sodir_wellbore_id,),
            )
            row = cur.fetchone()
            if row:
                total_depth, status, operator = row

        return CurrentWellState(
            well_id=well_id,
            dataset=dataset,
            timestamp=datetime.now(timezone.utc),
            latitude=loc.latitude,
            longitude=loc.longitude,
            current_depth_m=total_depth,
            current_formation=None,
            total_depth_m=total_depth,
            status=status,
            operator=operator,
            field_name=loc.field_name,
            is_simulated=False,
        )
    finally:
        if own_conn:
            conn.close()


def create_simulated_well(
    well_id: str,
    dataset: str,
    latitude: float,
    longitude: float,
    current_depth_m: Optional[float] = None,
    current_formation: Optional[str] = None,
    drilling_parameters: Optional[Dict[str, Any]] = None,
) -> CurrentWellState:
    """Create a simulated CurrentWellState for demo/testing purposes.

    The ``is_simulated`` flag is always True — consumers must check
    this before treating any field as a real observation.
    """
    return CurrentWellState(
        well_id=well_id,
        dataset=dataset,
        timestamp=datetime.now(timezone.utc),
        latitude=latitude,
        longitude=longitude,
        current_depth_m=current_depth_m,
        current_formation=current_formation,
        drilling_parameters=drilling_parameters or {},
        is_simulated=True,
    )
