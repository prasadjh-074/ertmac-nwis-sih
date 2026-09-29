"""Nearby-well search using Haversine geodesic distance.

Queries core.wellbore (via graph.well_identity_link for FORCE/Volve
wells) for location data.  All SQL uses parameterized placeholders.
No PostGIS dependency — distance is computed with the standard
Haversine formula in Python, which is accurate to <0.5% for the
inter-well distances on the Norwegian Continental Shelf.
"""

from __future__ import annotations

import math
from typing import List, Optional, Tuple

import psycopg2

from db_config import get_db_config

from .models import NearbyWellResult, WellLocation

DB_CONFIG = get_db_config()

EARTH_RADIUS_KM = 6371.0


def _get_connection():
    return psycopg2.connect(**DB_CONFIG)


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance between two points in kilometres."""
    rlat1, rlon1 = math.radians(lat1), math.radians(lon1)
    rlat2, rlon2 = math.radians(lat2), math.radians(lon2)
    dlat = rlat2 - rlat1
    dlon = rlon2 - rlon1
    a = math.sin(dlat / 2) ** 2 + math.cos(rlat1) * math.cos(rlat2) * math.sin(dlon / 2) ** 2
    return EARTH_RADIUS_KM * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def get_well_location(
    well_id: str,
    dataset: str,
    conn=None,
) -> Optional[WellLocation]:
    """Look up a single well's location via the identity bridge."""
    own_conn = conn is None
    if own_conn:
        conn = _get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT wil.well_id, wil.dataset,
                   wb.latitude, wb.longitude,
                   wb.wellbore_id, wb.wellbore_name,
                   f.field_name, f.field_id,
                   d.discovery_name, d.discovery_id
            FROM graph.well_identity_link wil
            JOIN core.wellbore wb ON wb.wellbore_id = wil.wellbore_id
            LEFT JOIN core.field f ON f.field_id = wb.field_id
            LEFT JOIN core.discovery d ON d.discovery_id = wb.discovery_id
            WHERE wil.well_id = %s AND wil.dataset = %s
            """,
            (well_id, dataset),
        )
        row = cur.fetchone()
        if row is None:
            return None
        return WellLocation(
            well_id=row[0],
            dataset=row[1],
            latitude=row[2],
            longitude=row[3],
            sodir_wellbore_id=row[4],
            sodir_wellbore_name=row[5],
            field_name=row[6],
            field_id=row[7],
            discovery_name=row[8],
            discovery_id=row[9],
        )
    finally:
        if own_conn:
            conn.close()


def _fetch_candidate_wells(
    dataset_filter: Optional[str],
    exclude_well: Optional[Tuple[str, str]],
    conn=None,
) -> List[dict]:
    """Fetch all wells with coordinates from the identity bridge.

    Returns dicts with keys matching NearbyWellResult fields.
    """
    own_conn = conn is None
    if own_conn:
        conn = _get_connection()
    try:
        cur = conn.cursor()
        clauses = []
        params: list = []

        if dataset_filter:
            clauses.append("wil.dataset = %s")
            params.append(dataset_filter)

        if exclude_well:
            clauses.append("NOT (wil.well_id = %s AND wil.dataset = %s)")
            params.extend(exclude_well)

        where = ("WHERE " + " AND ".join(clauses)) if clauses else ""

        cur.execute(
            f"""
            SELECT wil.well_id, wil.dataset,
                   wb.latitude, wb.longitude,
                   wb.wellbore_id, wb.wellbore_name,
                   f.field_name,
                   d.discovery_name
            FROM graph.well_identity_link wil
            JOIN core.wellbore wb ON wb.wellbore_id = wil.wellbore_id
            LEFT JOIN core.field f ON f.field_id = wb.field_id
            LEFT JOIN core.discovery d ON d.discovery_id = wb.discovery_id
            {where}
            """,
            params,
        )
        rows = cur.fetchall()
        return [
            {
                "well_id": r[0],
                "dataset": r[1],
                "latitude": r[2],
                "longitude": r[3],
                "sodir_wellbore_id": r[4],
                "sodir_wellbore_name": r[5],
                "field_name": r[6],
                "discovery_name": r[7],
            }
            for r in rows
            if r[2] is not None and r[3] is not None
        ]
    finally:
        if own_conn:
            conn.close()


def find_nearby_wells(
    well_id: str,
    dataset: str,
    radius_km: float = 50.0,
    limit: int = 10,
    dataset_filter: Optional[str] = None,
    conn=None,
) -> List[NearbyWellResult]:
    """Find wells within ``radius_km`` of the given well.

    Returns up to ``limit`` results, ordered by distance ascending
    (deterministic: ties broken by dataset then well_id).

    Raises ValueError if the reference well has no coordinates.
    """
    own_conn = conn is None
    if own_conn:
        conn = _get_connection()
    try:
        ref = get_well_location(well_id, dataset, conn=conn)
        if ref is None:
            raise ValueError(f"Well {dataset}:{well_id} not found in identity bridge")
        if not ref.has_coordinates:
            raise ValueError(f"Well {dataset}:{well_id} has no coordinates")

        return find_nearby_wells_by_coordinates(
            latitude=ref.latitude,
            longitude=ref.longitude,
            radius_km=radius_km,
            limit=limit,
            dataset_filter=dataset_filter,
            exclude_well=(well_id, dataset),
            conn=conn,
        )
    finally:
        if own_conn:
            conn.close()


def find_nearby_wells_by_coordinates(
    latitude: float,
    longitude: float,
    radius_km: float = 50.0,
    limit: int = 10,
    dataset_filter: Optional[str] = None,
    exclude_well: Optional[Tuple[str, str]] = None,
    conn=None,
) -> List[NearbyWellResult]:
    """Find wells within ``radius_km`` of the given coordinates.

    Returns up to ``limit`` results, ordered by distance ascending
    (deterministic: ties broken by dataset then well_id).
    """
    own_conn = conn is None
    if own_conn:
        conn = _get_connection()
    try:
        candidates = _fetch_candidate_wells(dataset_filter, exclude_well, conn=conn)

        scored = []
        for c in candidates:
            if c["latitude"] is None or c["longitude"] is None:
                continue
            if exclude_well and (c["well_id"], c["dataset"]) == exclude_well:
                continue
            d = haversine_km(latitude, longitude, c["latitude"], c["longitude"])
            if d <= radius_km:
                scored.append((d, c))

        scored.sort(key=lambda x: (x[0], x[1]["dataset"], x[1]["well_id"]))

        results = []
        for rank, (dist, c) in enumerate(scored[:limit], 1):
            results.append(NearbyWellResult(
                well_id=c["well_id"],
                dataset=c["dataset"],
                latitude=c["latitude"],
                longitude=c["longitude"],
                distance_km=round(dist, 3),
                sodir_wellbore_id=c["sodir_wellbore_id"],
                sodir_wellbore_name=c.get("sodir_wellbore_name"),
                field_name=c["field_name"],
                discovery_name=c["discovery_name"],
                rank=rank,
            ))
        return results
    finally:
        if own_conn:
            conn.close()
