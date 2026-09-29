"""Event storage and loading — read/write DrillingEvent rows in
subsurface.drilling_event.

All SQL uses parameterized placeholders.  No SQL is generated from
user input or LLM output.
"""

from __future__ import annotations

import json
from typing import List, Optional

import psycopg2

from db_config import get_db_config

from .models import DrillingEvent, EventProvenance, EventSeverity, EventType

DB_CONFIG = get_db_config()


def store_event(event: DrillingEvent, conn=None) -> int:
    """Insert a single event and return its event_id."""
    own_conn = conn is None
    if own_conn:
        conn = psycopg2.connect(**DB_CONFIG)
    try:
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO subsurface.drilling_event (
                well_id, dataset, event_type, subtype,
                depth_start_m, depth_end_m, formation, severity, description,
                source_type, source_table, source_record_id,
                source_document_id, source_chunk_id, source_file_name,
                extraction_method, extraction_confidence, raw_text_snippet,
                sodir_wellbore_id, metadata_json
            ) VALUES (
                %s, %s, %s, %s,
                %s, %s, %s, %s, %s,
                %s, %s, %s,
                %s, %s, %s,
                %s, %s, %s,
                %s, %s
            ) RETURNING event_id
            """,
            (
                event.well_id, event.dataset, event.event_type.value, event.subtype,
                event.depth_start_m, event.depth_end_m, event.formation,
                event.severity.value, event.description,
                event.provenance.source_type, event.provenance.source_table,
                event.provenance.source_record_id, event.provenance.source_document_id,
                event.provenance.source_chunk_id, event.provenance.source_file_name,
                event.provenance.extraction_method, event.provenance.extraction_confidence,
                event.provenance.raw_text_snippet,
                event.sodir_wellbore_id, json.dumps(event.metadata),
            ),
        )
        event_id = cur.fetchone()[0]
        if own_conn:
            conn.commit()
        return event_id
    finally:
        if own_conn:
            conn.close()


def store_events(events: List[DrillingEvent], conn=None) -> List[int]:
    """Batch-insert events.  Returns list of event_ids."""
    if not events:
        return []
    own_conn = conn is None
    if own_conn:
        conn = psycopg2.connect(**DB_CONFIG)
    try:
        cur = conn.cursor()
        ids = []
        for event in events:
            cur.execute(
                """
                INSERT INTO subsurface.drilling_event (
                    well_id, dataset, event_type, subtype,
                    depth_start_m, depth_end_m, formation, severity, description,
                    source_type, source_table, source_record_id,
                    source_document_id, source_chunk_id, source_file_name,
                    extraction_method, extraction_confidence, raw_text_snippet,
                    sodir_wellbore_id, metadata_json
                ) VALUES (
                    %s, %s, %s, %s,
                    %s, %s, %s, %s, %s,
                    %s, %s, %s,
                    %s, %s, %s,
                    %s, %s, %s,
                    %s, %s
                ) RETURNING event_id
                """,
                (
                    event.well_id, event.dataset, event.event_type.value, event.subtype,
                    event.depth_start_m, event.depth_end_m, event.formation,
                    event.severity.value, event.description,
                    event.provenance.source_type, event.provenance.source_table,
                    event.provenance.source_record_id, event.provenance.source_document_id,
                    event.provenance.source_chunk_id, event.provenance.source_file_name,
                    event.provenance.extraction_method, event.provenance.extraction_confidence,
                    event.provenance.raw_text_snippet,
                    event.sodir_wellbore_id, json.dumps(event.metadata),
                ),
            )
            ids.append(cur.fetchone()[0])
        if own_conn:
            conn.commit()
        return ids
    finally:
        if own_conn:
            conn.close()


def _row_to_event(row: tuple) -> DrillingEvent:
    """Convert a DB row to a DrillingEvent."""
    return DrillingEvent(
        event_id=row[0],
        well_id=row[1],
        dataset=row[2],
        event_type=EventType(row[3]),
        subtype=row[4],
        depth_start_m=row[5],
        depth_end_m=row[6],
        formation=row[7],
        severity=EventSeverity(row[8]),
        description=row[9],
        provenance=EventProvenance(
            source_type=row[10],
            source_table=row[11],
            source_record_id=row[12],
            source_document_id=row[13],
            source_chunk_id=row[14],
            source_file_name=row[15],
            extraction_method=row[16],
            extraction_confidence=row[17],
            raw_text_snippet=row[18],
        ),
        sodir_wellbore_id=row[19],
        metadata=row[20] if row[20] else {},
    )


_SELECT_COLS = """
    event_id, well_id, dataset, event_type, subtype,
    depth_start_m, depth_end_m, formation, severity, description,
    source_type, source_table, source_record_id,
    source_document_id, source_chunk_id, source_file_name,
    extraction_method, extraction_confidence, raw_text_snippet,
    sodir_wellbore_id, metadata_json
"""


def load_events_for_well(
    well_id: str,
    dataset: str,
    event_type: Optional[EventType] = None,
    conn=None,
) -> List[DrillingEvent]:
    """Load stored events for a well, optionally filtered by type."""
    own_conn = conn is None
    if own_conn:
        conn = psycopg2.connect(**DB_CONFIG)
    try:
        cur = conn.cursor()
        if event_type:
            cur.execute(
                f"SELECT {_SELECT_COLS} FROM subsurface.drilling_event "
                "WHERE well_id = %s AND dataset = %s AND event_type = %s "
                "ORDER BY depth_start_m NULLS LAST, event_id",
                (well_id, dataset, event_type.value),
            )
        else:
            cur.execute(
                f"SELECT {_SELECT_COLS} FROM subsurface.drilling_event "
                "WHERE well_id = %s AND dataset = %s "
                "ORDER BY depth_start_m NULLS LAST, event_id",
                (well_id, dataset),
            )
        return [_row_to_event(row) for row in cur.fetchall()]
    finally:
        if own_conn:
            conn.close()


def load_events_by_wells(
    well_ids: List[tuple],
    event_type: Optional[EventType] = None,
    conn=None,
) -> List[DrillingEvent]:
    """Load events for multiple wells.  well_ids is a list of (well_id, dataset) tuples."""
    if not well_ids:
        return []
    own_conn = conn is None
    if own_conn:
        conn = psycopg2.connect(**DB_CONFIG)
    try:
        cur = conn.cursor()
        placeholders = ",".join(["(%s, %s)"] * len(well_ids))
        params = []
        for wid, ds in well_ids:
            params.extend([wid, ds])

        type_filter = ""
        if event_type:
            type_filter = " AND event_type = %s"
            params.append(event_type.value)

        cur.execute(
            f"SELECT {_SELECT_COLS} FROM subsurface.drilling_event "
            f"WHERE (well_id, dataset) IN ({placeholders}){type_filter} "
            "ORDER BY well_id, depth_start_m NULLS LAST, event_id",
            params,
        )
        return [_row_to_event(row) for row in cur.fetchall()]
    finally:
        if own_conn:
            conn.close()


def find_events_near_depth(
    well_id: str,
    dataset: str,
    target_depth_m: float,
    tolerance_m: float = 100.0,
    event_type: Optional[EventType] = None,
    conn=None,
) -> List[DrillingEvent]:
    """Find events near a target depth with a tolerance window."""
    own_conn = conn is None
    if own_conn:
        conn = psycopg2.connect(**DB_CONFIG)
    try:
        cur = conn.cursor()
        params: list = [well_id, dataset, target_depth_m - tolerance_m, target_depth_m + tolerance_m]
        type_filter = ""
        if event_type:
            type_filter = " AND event_type = %s"
            params.append(event_type.value)

        cur.execute(
            f"SELECT {_SELECT_COLS} FROM subsurface.drilling_event "
            "WHERE well_id = %s AND dataset = %s "
            "AND depth_start_m >= %s AND depth_start_m <= %s"
            f"{type_filter} "
            "ORDER BY ABS(depth_start_m - %s), event_id",
            params + [target_depth_m],
        )
        return [_row_to_event(row) for row in cur.fetchall()]
    finally:
        if own_conn:
            conn.close()


def find_events_by_formation(
    formation: str,
    well_id: Optional[str] = None,
    dataset: Optional[str] = None,
    event_type: Optional[EventType] = None,
    conn=None,
) -> List[DrillingEvent]:
    """Find events associated with a specific formation."""
    own_conn = conn is None
    if own_conn:
        conn = psycopg2.connect(**DB_CONFIG)
    try:
        cur = conn.cursor()
        where_clauses = ["LOWER(formation) = LOWER(%s)"]
        params: list = [formation]

        if well_id:
            where_clauses.append("well_id = %s")
            params.append(well_id)
        if dataset:
            where_clauses.append("dataset = %s")
            params.append(dataset)
        if event_type:
            where_clauses.append("event_type = %s")
            params.append(event_type.value)

        where = " AND ".join(where_clauses)
        cur.execute(
            f"SELECT {_SELECT_COLS} FROM subsurface.drilling_event "
            f"WHERE {where} "
            "ORDER BY well_id, depth_start_m NULLS LAST, event_id",
            params,
        )
        return [_row_to_event(row) for row in cur.fetchall()]
    finally:
        if own_conn:
            conn.close()


def delete_events_for_well(well_id: str, dataset: str, conn=None) -> int:
    """Delete all events for a well.  Returns count of deleted rows."""
    own_conn = conn is None
    if own_conn:
        conn = psycopg2.connect(**DB_CONFIG)
    try:
        cur = conn.cursor()
        cur.execute(
            "DELETE FROM subsurface.drilling_event WHERE well_id = %s AND dataset = %s",
            (well_id, dataset),
        )
        count = cur.rowcount
        if own_conn:
            conn.commit()
        return count
    finally:
        if own_conn:
            conn.close()


def count_events(conn=None) -> int:
    """Return total number of stored events."""
    own_conn = conn is None
    if own_conn:
        conn = psycopg2.connect(**DB_CONFIG)
    try:
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM subsurface.drilling_event")
        return cur.fetchone()[0]
    finally:
        if own_conn:
            conn.close()
