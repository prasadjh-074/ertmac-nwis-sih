"""Historical drilling event intelligence."""

from .models import DrillingEvent, EventType, EventSeverity, EventProvenance, CorrelatedEvent
from .extraction import (
    extract_events_from_text,
    extract_events_for_well,
    extract_all_linked_well_events,
    clean_html,
)
from .storage import (
    store_event,
    store_events,
    load_events_for_well,
    load_events_by_wells,
    find_events_near_depth,
    find_events_by_formation,
    delete_events_for_well,
    count_events,
)
from .correlation import correlate_historical_events

__all__ = [
    "DrillingEvent",
    "EventType",
    "EventSeverity",
    "EventProvenance",
    "CorrelatedEvent",
    "extract_events_from_text",
    "extract_events_for_well",
    "extract_all_linked_well_events",
    "clean_html",
    "store_event",
    "store_events",
    "load_events_for_well",
    "load_events_by_wells",
    "find_events_near_depth",
    "find_events_by_formation",
    "delete_events_for_well",
    "count_events",
    "correlate_historical_events",
]
