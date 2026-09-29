"""Deterministic drilling event extraction from SODIR wellbore history.

Uses regex/keyword dictionaries to identify canonical drilling events
in wellbore_history.history_text.  Reuses ingestion/nlp/entity_extractor
for depth and formation extraction within event context windows.

Every extracted event retains full source provenance.  Uncertain
extractions carry lower confidence scores.
"""

from __future__ import annotations

import re
from typing import List, Optional, Tuple

from .models import (
    DrillingEvent,
    EventProvenance,
    EventSeverity,
    EventType,
)

_HTML_TAG_RE = re.compile(r"<[^>]+>")
_MULTI_SPACE_RE = re.compile(r"\s+")

_DEPTH_RE = re.compile(
    r"(?:at|from|to|around|near|below|above|between)?\s*"
    r"(\d{2,5}(?:\.\d+)?)\s*(?:m\b|meters?\b|mMD\b|mTVD\b)",
    re.IGNORECASE,
)

_DEPTH_RANGE_RE = re.compile(
    r"(\d{2,5}(?:\.\d+)?)\s*[-–]\s*(\d{2,5}(?:\.\d+)?)\s*(?:m\b|meters?\b)",
    re.IGNORECASE,
)


# --- Event type keyword patterns ---
# Each tuple: (EventType, compiled regex, confidence, severity_hint, exclude_pattern)

_EVENT_PATTERNS: List[Tuple[EventType, re.Pattern, float, EventSeverity, Optional[re.Pattern]]] = [
    (
        EventType.STUCK_PIPE,
        re.compile(r"\bstuck\s+pipe\b", re.IGNORECASE),
        0.90, EventSeverity.HIGH, None,
    ),
    (
        EventType.STUCK_PIPE,
        re.compile(r"\bbit\s+(?:got\s+)?stuck\b", re.IGNORECASE),
        0.85, EventSeverity.HIGH, None,
    ),
    (
        EventType.STUCK_PIPE,
        re.compile(r"\bdifferential(?:ly)?\s+stuck(?:ing)?\b", re.IGNORECASE),
        0.90, EventSeverity.HIGH, None,
    ),
    (
        EventType.MUD_LOSS,
        re.compile(r"\bmud\s+loss(?:es)?\b", re.IGNORECASE),
        0.90, EventSeverity.MEDIUM, None,
    ),
    (
        EventType.MUD_LOSS,
        re.compile(r"\blost\s+circulation\b", re.IGNORECASE),
        0.90, EventSeverity.MEDIUM, None,
    ),
    (
        EventType.MUD_LOSS,
        re.compile(r"\bsevere\s+(?:mud\s+)?loss(?:es)?\b", re.IGNORECASE),
        0.90, EventSeverity.HIGH, None,
    ),
    (
        EventType.MUD_LOSS,
        re.compile(r"\btotal\s+(?:mud\s+)?loss(?:es)?\b", re.IGNORECASE),
        0.90, EventSeverity.CRITICAL, None,
    ),
    (
        EventType.KICK,
        re.compile(r"\bwell\s+(?:control\s+)?kick\b", re.IGNORECASE),
        0.90, EventSeverity.CRITICAL, None,
    ),
    (
        EventType.KICK,
        re.compile(r"\bkick\b", re.IGNORECASE),
        0.60, EventSeverity.HIGH,
        # Exclude "kick-off" / "kicked off" (sidetrack operations, not well control)
        re.compile(r"\bkick[- ]?off\b|\bkicked\s+off\b", re.IGNORECASE),
    ),
    (
        EventType.OVERPRESSURE,
        re.compile(r"\bover\s*pressur(?:e|ed|ized)\b", re.IGNORECASE),
        0.85, EventSeverity.HIGH, None,
    ),
    (
        EventType.OVERPRESSURE,
        re.compile(r"\babnormal(?:ly)?\s+high\s+pressure\b", re.IGNORECASE),
        0.85, EventSeverity.HIGH, None,
    ),
    (
        EventType.OVERPRESSURE,
        re.compile(r"\bpore\s+pressure\s+(?:increase|higher|exceeded)\b", re.IGNORECASE),
        0.80, EventSeverity.MEDIUM, None,
    ),
    (
        EventType.TORQUE_SPIKE,
        re.compile(r"\btorque\s+(?:spike|increase|problem|erratic)\b", re.IGNORECASE),
        0.80, EventSeverity.MEDIUM, None,
    ),
    (
        EventType.TORQUE_SPIKE,
        re.compile(r"\bhigh\s+torque\b", re.IGNORECASE),
        0.75, EventSeverity.MEDIUM, None,
    ),
    (
        EventType.CEMENTING_ISSUE,
        re.compile(r"\bcement(?:ing)?\s+(?:failure|problem|issue|squeeze|remedial)\b", re.IGNORECASE),
        0.85, EventSeverity.MEDIUM, None,
    ),
    (
        EventType.CEMENTING_ISSUE,
        re.compile(r"\bfailed\s+cement(?:ing)?\b", re.IGNORECASE),
        0.85, EventSeverity.HIGH, None,
    ),
    (
        EventType.CASING_ISSUE,
        re.compile(r"\bcasing\s+(?:failure|leak|collapse|damage|problem|stuck)\b", re.IGNORECASE),
        0.85, EventSeverity.HIGH, None,
    ),
    (
        EventType.FISHING,
        re.compile(r"\bfishing\s+(?:operation|job|attempt)\b", re.IGNORECASE),
        0.90, EventSeverity.MEDIUM, None,
    ),
    (
        EventType.FISHING,
        re.compile(r"\bfishing\b", re.IGNORECASE),
        0.75, EventSeverity.MEDIUM,
        # Exclude references like "fishing industry" or "fishing vessel"
        re.compile(r"\bfishing\s+(?:industry|vessel|boat|ground)\b", re.IGNORECASE),
    ),
    (
        EventType.FISHING,
        re.compile(r"\blost\s+in\s+hole\b", re.IGNORECASE),
        0.85, EventSeverity.HIGH, None,
    ),
    (
        EventType.NPT,
        re.compile(r"\bNPT\b"),
        0.80, EventSeverity.MEDIUM, None,
    ),
    (
        EventType.NPT,
        re.compile(r"\bnon[- ]?productive\s+time\b", re.IGNORECASE),
        0.85, EventSeverity.MEDIUM, None,
    ),
    (
        EventType.OTHER,
        re.compile(r"\btight\s+hole\b", re.IGNORECASE),
        0.70, EventSeverity.LOW, None,
    ),
    (
        EventType.OTHER,
        re.compile(r"\bhole\s+(?:instability|collapse|washout)\b", re.IGNORECASE),
        0.75, EventSeverity.MEDIUM, None,
    ),
    (
        EventType.OTHER,
        re.compile(r"\bjunked\s+and\s+abandoned\b", re.IGNORECASE),
        0.90, EventSeverity.CRITICAL, None,
    ),
]

# Severity escalation keywords
_SEVERITY_ESCALATORS = [
    (re.compile(r"\bsevere\b", re.IGNORECASE), EventSeverity.HIGH),
    (re.compile(r"\bmajor\b", re.IGNORECASE), EventSeverity.HIGH),
    (re.compile(r"\btotal\s+loss\b", re.IGNORECASE), EventSeverity.CRITICAL),
    (re.compile(r"\bjunked\b|\babandoned\b|\bsidetrack\b", re.IGNORECASE), EventSeverity.HIGH),
]


def clean_html(text: str) -> str:
    """Strip HTML tags and normalize whitespace."""
    text = _HTML_TAG_RE.sub(" ", text)
    text = text.replace("&quot;", '"').replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
    return _MULTI_SPACE_RE.sub(" ", text).strip()


def _extract_context_window(text: str, match_start: int, match_end: int, window: int = 200) -> str:
    """Return text around a match for context extraction."""
    start = max(0, match_start - window)
    end = min(len(text), match_end + window)
    return text[start:end]


def _extract_depths_from_context(context: str) -> Tuple[Optional[float], Optional[float]]:
    """Extract depth values from event context text."""
    range_match = _DEPTH_RANGE_RE.search(context)
    if range_match:
        return float(range_match.group(1)), float(range_match.group(2))

    depths = []
    for m in _DEPTH_RE.finditer(context):
        try:
            depths.append(float(m.group(1)))
        except (ValueError, IndexError):
            continue

    if len(depths) >= 2:
        return min(depths), max(depths)
    elif len(depths) == 1:
        return depths[0], None
    return None, None


def _extract_formation_from_context(context: str) -> Optional[str]:
    """Extract formation name from event context, reusing the ingestion
    entity extractor's patterns."""
    from ingestion.nlp.entity_extractor import FORMATION_SUFFIX_RE, _formation_lookup

    m = FORMATION_SUFFIX_RE.search(context)
    if m:
        return m.group(1)

    try:
        pattern, flat = _formation_lookup()
        fm = pattern.search(context)
        if fm:
            return flat.get(fm.group(0).lower(), fm.group(0))
    except Exception:
        pass

    return None


def _escalate_severity(
    base_severity: EventSeverity,
    context: str,
) -> EventSeverity:
    """Check for severity-escalating keywords in context."""
    severity_order = [EventSeverity.LOW, EventSeverity.MEDIUM, EventSeverity.HIGH, EventSeverity.CRITICAL]
    current_idx = severity_order.index(base_severity) if base_severity in severity_order else 0

    for pattern, escalated in _SEVERITY_ESCALATORS:
        if pattern.search(context):
            esc_idx = severity_order.index(escalated) if escalated in severity_order else 0
            current_idx = max(current_idx, esc_idx)

    return severity_order[current_idx]


def extract_events_from_text(
    text: str,
    well_id: str,
    dataset: str,
    sodir_wellbore_id: Optional[int] = None,
    source_record_id: Optional[int] = None,
) -> List[DrillingEvent]:
    """Extract drilling events from a single history text.

    Returns a list of DrillingEvent objects with full provenance.
    Each event is extracted deterministically — no LLM is used.
    """
    clean = clean_html(text)
    if not clean or len(clean) < 20:
        return []

    events: List[DrillingEvent] = []
    seen_spans: List[Tuple[int, int, EventType]] = []

    for event_type, pattern, confidence, severity_hint, exclude_pattern in _EVENT_PATTERNS:
        for m in pattern.finditer(clean):
            if exclude_pattern and exclude_pattern.search(
                clean[max(0, m.start() - 30):min(len(clean), m.end() + 30)]
            ):
                continue

            # Deduplicate: skip if we already have the same event type
            # covering an overlapping text span
            overlapping = False
            for s_start, s_end, s_type in seen_spans:
                if s_type == event_type and not (m.end() <= s_start or m.start() >= s_end):
                    overlapping = True
                    break
            if overlapping:
                continue
            seen_spans.append((m.start(), m.end(), event_type))

            context = _extract_context_window(clean, m.start(), m.end())
            depth_start, depth_end = _extract_depths_from_context(context)
            formation = _extract_formation_from_context(context)
            severity = _escalate_severity(severity_hint, context)

            snippet = clean[max(0, m.start() - 50):min(len(clean), m.end() + 100)]

            events.append(DrillingEvent(
                well_id=well_id,
                dataset=dataset,
                event_type=event_type,
                subtype=m.group(0).strip(),
                depth_start_m=depth_start,
                depth_end_m=depth_end,
                formation=formation,
                severity=severity,
                description=snippet,
                provenance=EventProvenance(
                    source_type="sodir_history",
                    source_table="subsurface.wellbore_history",
                    source_record_id=source_record_id,
                    extraction_method="regex_keyword",
                    extraction_confidence=confidence,
                    raw_text_snippet=snippet,
                ),
                sodir_wellbore_id=sodir_wellbore_id,
            ))

    return events


def extract_events_for_well(
    well_id: str,
    dataset: str,
    conn=None,
) -> List[DrillingEvent]:
    """Extract drilling events from all SODIR history records for a well."""
    import psycopg2

    from db_config import get_db_config

    DB_CONFIG = get_db_config()
    own_conn = conn is None
    if own_conn:
        conn = psycopg2.connect(**DB_CONFIG)
    try:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT wh.history_id, wh.wellbore_id, wh.history_text
            FROM subsurface.wellbore_history wh
            JOIN graph.well_identity_link wil ON wil.wellbore_id = wh.wellbore_id
            WHERE wil.well_id = %s AND wil.dataset = %s
              AND wh.history_text IS NOT NULL
            """,
            (well_id, dataset),
        )
        all_events = []
        for history_id, wellbore_id, history_text in cur.fetchall():
            events = extract_events_from_text(
                text=history_text,
                well_id=well_id,
                dataset=dataset,
                sodir_wellbore_id=wellbore_id,
                source_record_id=history_id,
            )
            all_events.extend(events)
        return all_events
    finally:
        if own_conn:
            conn.close()


def extract_all_linked_well_events(conn=None) -> List[DrillingEvent]:
    """Extract events from all linked wells' history records.

    Used for batch population of the drilling_events table.
    """
    import psycopg2

    from db_config import get_db_config

    DB_CONFIG = get_db_config()
    own_conn = conn is None
    if own_conn:
        conn = psycopg2.connect(**DB_CONFIG)
    try:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT wil.well_id, wil.dataset, wh.history_id, wh.wellbore_id, wh.history_text
            FROM subsurface.wellbore_history wh
            JOIN graph.well_identity_link wil ON wil.wellbore_id = wh.wellbore_id
            WHERE wh.history_text IS NOT NULL
            """
        )
        all_events = []
        for well_id, dataset, history_id, wellbore_id, history_text in cur.fetchall():
            events = extract_events_from_text(
                text=history_text,
                well_id=well_id,
                dataset=dataset,
                sodir_wellbore_id=wellbore_id,
                source_record_id=history_id,
            )
            all_events.extend(events)
        return all_events
    finally:
        if own_conn:
            conn.close()
