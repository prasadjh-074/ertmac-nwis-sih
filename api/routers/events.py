"""Historical drilling event endpoints.

  GET /events/well         — all events for a well
  GET /events/near-depth   — events near a target depth
  GET /events/formation    — events by formation name
  GET /events/correlated   — full correlated view (own well + nearby +
                              depth + formation), used by the risk
                              engine

The event catalog is populated deterministically from SODIR
wellbore-history text by events/extraction.py; this router exposes
that pre-extracted data — it never re-runs the extractor on the hot path.
"""

from __future__ import annotations

import logging
from dataclasses import asdict
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from events.correlation import correlate_historical_events
from events.models import EventType
from events.storage import (
    find_events_by_formation,
    find_events_near_depth,
    load_events_for_well,
)

from ..deps import get_conn

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/events", tags=["events"])


class EventResponse(BaseModel):
    event_type: str
    severity: str
    description: Optional[str] = None
    depth_start_m: Optional[float] = None
    depth_end_m: Optional[float] = None
    formation: Optional[str] = None
    well_id: Optional[str] = None
    dataset: Optional[str] = None
    subtype: Optional[str] = None
    provenance: Optional[Dict[str, Any]] = None


class EventListResponse(BaseModel):
    count: int
    events: List[EventResponse]


class CorrelatedEventResponse(BaseModel):
    event: EventResponse
    source_well_id: str
    source_dataset: str
    distance_km: Optional[float] = None
    depth_overlap: bool = False
    depth_difference_m: Optional[float] = None
    formation_match: bool = False
    relevance_factors: Dict[str, Any] = Field(default_factory=dict)


class CorrelatedEventListResponse(BaseModel):
    reference_well: str
    reference_dataset: str
    count: int
    events: List[CorrelatedEventResponse]


def _event_type_or_400(raw: Optional[str]) -> Optional[EventType]:
    if raw is None:
        return None
    try:
        return EventType(raw)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"invalid event_type '{raw}'. valid: {[e.value for e in EventType]}",
        )


def _event_to_response(ev) -> EventResponse:
    prov = None
    if ev.provenance is not None:
        prov_dict = asdict(ev.provenance)
        # Never emit raw source_record_id or extraction internals that
        # aren't useful to clients; keep the trace back to the source
        # table + method + confidence + snippet.
        prov = {
            "source_type": prov_dict.get("source_type"),
            "source_table": prov_dict.get("source_table"),
            "extraction_method": prov_dict.get("extraction_method"),
            "extraction_confidence": prov_dict.get("extraction_confidence"),
            "raw_text_snippet": prov_dict.get("raw_text_snippet"),
        }
    return EventResponse(
        event_type=ev.event_type.value,
        severity=ev.severity.value,
        description=ev.description,
        depth_start_m=ev.depth_start_m,
        depth_end_m=ev.depth_end_m,
        formation=ev.formation,
        well_id=getattr(ev, "well_id", None),
        dataset=getattr(ev, "dataset", None),
        subtype=getattr(ev, "subtype", None),
        provenance=prov,
    )


@router.get("/well", response_model=EventListResponse)
def get_events_for_well(
    dataset: str = Query(...),
    well_id: str = Query(...),
    event_type: Optional[str] = Query(None, description="Filter by canonical event type"),
    conn=Depends(get_conn),
):
    try:
        events = load_events_for_well(
            well_id=well_id, dataset=dataset,
            event_type=_event_type_or_400(event_type), conn=conn,
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("load_events_for_well failed: %s", exc)
        raise HTTPException(status_code=500, detail="events lookup failed")
    return EventListResponse(count=len(events), events=[_event_to_response(e) for e in events])


@router.get("/near-depth", response_model=EventListResponse)
def get_events_near_depth(
    dataset: str = Query(...),
    well_id: str = Query(...),
    depth_m: float = Query(..., ge=0),
    tolerance_m: float = Query(100.0, gt=0, le=2000),
    event_type: Optional[str] = Query(None),
    conn=Depends(get_conn),
):
    events = find_events_near_depth(
        well_id=well_id, dataset=dataset,
        target_depth_m=depth_m, tolerance_m=tolerance_m,
        event_type=_event_type_or_400(event_type), conn=conn,
    )
    return EventListResponse(count=len(events), events=[_event_to_response(e) for e in events])


@router.get("/formation", response_model=EventListResponse)
def get_events_by_formation(
    formation: str = Query(..., min_length=1, max_length=100),
    dataset: Optional[str] = Query(None),
    well_id: Optional[str] = Query(None),
    event_type: Optional[str] = Query(None),
    conn=Depends(get_conn),
):
    events = find_events_by_formation(
        formation=formation, dataset=dataset, well_id=well_id,
        event_type=_event_type_or_400(event_type), conn=conn,
    )
    return EventListResponse(count=len(events), events=[_event_to_response(e) for e in events])


@router.get("/correlated", response_model=CorrelatedEventListResponse)
def get_correlated_events(
    dataset: str = Query(...),
    well_id: str = Query(...),
    current_depth_m: Optional[float] = Query(None, ge=0),
    current_formation: Optional[str] = Query(None, max_length=100),
    radius_km: float = Query(50.0, gt=0, le=500),
    limit: int = Query(20, ge=1, le=200),
    event_type: Optional[str] = Query(None),
    conn=Depends(get_conn),
):
    try:
        correlated = correlate_historical_events(
            well_id=well_id, dataset=dataset,
            current_depth_m=current_depth_m,
            current_formation=current_formation,
            radius_km=radius_km, limit=limit,
            event_type=_event_type_or_400(event_type),
            conn=conn,
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("correlate_historical_events failed: %s", exc)
        raise HTTPException(status_code=500, detail="event correlation failed")

    body_events = [
        CorrelatedEventResponse(
            event=_event_to_response(c.event),
            source_well_id=c.source_well_id,
            source_dataset=c.source_dataset,
            distance_km=c.distance_km,
            depth_overlap=c.depth_overlap,
            depth_difference_m=c.depth_difference_m,
            formation_match=c.formation_match,
            relevance_factors=c.relevance_factors,
        )
        for c in correlated
    ]
    return CorrelatedEventListResponse(
        reference_well=well_id, reference_dataset=dataset,
        count=len(body_events), events=body_events,
    )
