"""Historical drilling event correlation service.

Combines nearby-well proximity, geological similarity, depth correlation,
and formation matching to find historically relevant drilling events
for a given well context.
"""

from __future__ import annotations

from typing import Dict, List, Optional

from .models import CorrelatedEvent, DrillingEvent, EventType
from .storage import (
    find_events_by_formation,
    find_events_near_depth,
    load_events_by_wells,
    load_events_for_well,
)


def correlate_historical_events(
    well_id: str,
    dataset: str,
    current_depth_m: Optional[float] = None,
    current_formation: Optional[str] = None,
    radius_km: float = 50.0,
    depth_tolerance_m: float = 100.0,
    limit: int = 20,
    event_type: Optional[EventType] = None,
    include_own_well: bool = True,
    conn=None,
) -> List[CorrelatedEvent]:
    """Find historically relevant drilling events for a well context.

    Combines:
    1. Events from the well itself
    2. Events from nearby wells (geographic proximity)
    3. Events matching the current depth (within tolerance)
    4. Events matching the current formation

    Each result is scored by relevance factors and sorted.
    """
    import psycopg2
    from nearby.search import find_nearby_wells, get_well_location

    from db_config import get_db_config

    DB_CONFIG = get_db_config()
    own_conn = conn is None
    if own_conn:
        conn = psycopg2.connect(**DB_CONFIG)

    try:
        correlated: Dict[int, CorrelatedEvent] = {}

        location = get_well_location(well_id, dataset, conn=conn)

        # 1. Own well events
        if include_own_well:
            own_events = load_events_for_well(well_id, dataset, event_type=event_type, conn=conn)
            for ev in own_events:
                depth_overlap = False
                depth_diff = None
                if current_depth_m is not None and ev.depth_start_m is not None:
                    depth_diff = abs(current_depth_m - ev.depth_start_m)
                    depth_overlap = depth_diff <= depth_tolerance_m

                formation_match = (
                    current_formation is not None
                    and ev.formation is not None
                    and ev.formation.lower() == current_formation.lower()
                )

                correlated[id(ev)] = CorrelatedEvent(
                    event=ev,
                    source_well_id=well_id,
                    source_dataset=dataset,
                    distance_km=0.0,
                    geological_similarity=1.0,
                    depth_overlap=depth_overlap,
                    depth_difference_m=depth_diff,
                    formation_match=formation_match,
                    relevance_factors={"own_well": True},
                )

        # 2. Nearby well events
        nearby_wells = []
        if location and location.has_coordinates:
            try:
                nearby_wells = find_nearby_wells(
                    well_id, dataset, radius_km=radius_km, limit=50, conn=conn,
                )
            except ValueError:
                pass

        if nearby_wells:
            nearby_ids = [(n.well_id, n.dataset) for n in nearby_wells]
            distance_map = {(n.well_id, n.dataset): n.distance_km for n in nearby_wells}
            nearby_events = load_events_by_wells(nearby_ids, event_type=event_type, conn=conn)

            for ev in nearby_events:
                dist = distance_map.get((ev.well_id, ev.dataset), None)
                depth_overlap = False
                depth_diff = None
                if current_depth_m is not None and ev.depth_start_m is not None:
                    depth_diff = abs(current_depth_m - ev.depth_start_m)
                    depth_overlap = depth_diff <= depth_tolerance_m

                formation_match = (
                    current_formation is not None
                    and ev.formation is not None
                    and ev.formation.lower() == current_formation.lower()
                )

                correlated[id(ev)] = CorrelatedEvent(
                    event=ev,
                    source_well_id=ev.well_id,
                    source_dataset=ev.dataset,
                    distance_km=dist,
                    depth_overlap=depth_overlap,
                    depth_difference_m=depth_diff,
                    formation_match=formation_match,
                    relevance_factors={"nearby_well": True, "distance_km": dist},
                )

        # 3. Formation-matched events from any well
        if current_formation:
            formation_events = find_events_by_formation(
                current_formation, event_type=event_type, conn=conn,
            )
            for ev in formation_events:
                key = ev.event_id if ev.event_id else id(ev)
                if key in correlated:
                    correlated[key].formation_match = True
                    correlated[key].relevance_factors["formation_match"] = True
                    continue

                depth_overlap = False
                depth_diff = None
                if current_depth_m is not None and ev.depth_start_m is not None:
                    depth_diff = abs(current_depth_m - ev.depth_start_m)
                    depth_overlap = depth_diff <= depth_tolerance_m

                correlated[key] = CorrelatedEvent(
                    event=ev,
                    source_well_id=ev.well_id,
                    source_dataset=ev.dataset,
                    formation_match=True,
                    depth_overlap=depth_overlap,
                    depth_difference_m=depth_diff,
                    relevance_factors={"formation_match": True},
                )

        # Score and sort
        results = list(correlated.values())
        for r in results:
            r.relevance_factors["score"] = _compute_relevance_score(r, radius_km)
        results.sort(key=lambda r: r.relevance_factors.get("score", 0), reverse=True)

        return results[:limit]

    finally:
        if own_conn:
            conn.close()


def _compute_relevance_score(corr: CorrelatedEvent, radius_km: float) -> float:
    """Compute a transparent relevance score from individual factors."""
    score = 0.0

    # Own well bonus
    if corr.relevance_factors.get("own_well"):
        score += 0.3

    # Distance proximity (closer = higher)
    if corr.distance_km is not None and radius_km > 0:
        score += 0.25 * max(0.0, 1.0 - corr.distance_km / radius_km)

    # Depth overlap
    if corr.depth_overlap:
        score += 0.25

    # Formation match
    if corr.formation_match:
        score += 0.2

    # Extraction confidence
    score *= max(0.5, corr.event.provenance.extraction_confidence)

    return round(score, 4)
