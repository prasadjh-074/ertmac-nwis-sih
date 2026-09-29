"""Additional evidence sources for risk scoring.

Pulls DST pressure, mud weight, casing, and petrophysical features
from the SODIR database and unified feature set to enrich risk
assessments beyond event-only correlation.

All SQL uses parameterized placeholders.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import psycopg2

from db_config import get_db_config

DB_CONFIG = get_db_config()


@dataclass
class PressureEvidence:
    wellbore_id: int
    well_id: str
    dataset: str
    from_depth_m: Optional[float]
    to_depth_m: Optional[float]
    shut_in_pressure: float
    flow_pressure: float
    bottom_hole_pressure: float
    distance_km: Optional[float] = None


@dataclass
class MudWeightEvidence:
    wellbore_id: int
    well_id: str
    dataset: str
    depth_m: float
    mud_weight: float
    mud_type: Optional[str] = None
    distance_km: Optional[float] = None


@dataclass
class CaliperEvidence:
    well_id: str
    dataset: str
    depth_start_m: float
    depth_end_m: float
    caliper_mean: float
    caliper_max: float
    bit_size_mean: Optional[float] = None
    washout_ratio: Optional[float] = None


@dataclass
class WellEvidenceSummary:
    """Aggregated evidence from multiple sources for one well context."""
    pressure_evidence: List[PressureEvidence] = field(default_factory=list)
    mud_weight_evidence: List[MudWeightEvidence] = field(default_factory=list)
    caliper_evidence: List[CaliperEvidence] = field(default_factory=list)
    max_pressure_psi: Optional[float] = None
    avg_mud_weight: Optional[float] = None
    max_washout_ratio: Optional[float] = None
    evidence_summary: List[str] = field(default_factory=list)


def get_dst_pressure_for_nearby_wells(
    nearby_wellbore_ids: List[Tuple[int, str, str, Optional[float]]],
    target_depth_m: Optional[float] = None,
    depth_tolerance_m: float = 500.0,
    conn=None,
) -> List[PressureEvidence]:
    """Fetch DST pressure data for nearby wells, optionally filtered by depth.

    nearby_wellbore_ids: list of (sodir_wellbore_id, well_id, dataset, distance_km)
    """
    if not nearby_wellbore_ids:
        return []

    own_conn = conn is None
    if own_conn:
        conn = psycopg2.connect(**DB_CONFIG)
    try:
        cur = conn.cursor()
        wb_ids = [n[0] for n in nearby_wellbore_ids]
        wb_map = {n[0]: (n[1], n[2], n[3]) for n in nearby_wellbore_ids}

        placeholders = ",".join(["%s"] * len(wb_ids))
        params: list = list(wb_ids)

        depth_filter = ""
        if target_depth_m is not None:
            depth_filter = " AND from_depth_m >= %s AND from_depth_m <= %s"
            params.extend([target_depth_m - depth_tolerance_m, target_depth_m + depth_tolerance_m])

        cur.execute(
            f"""SELECT wellbore_id, from_depth_m, to_depth_m,
                       final_shut_in_pressure, final_flow_pressure, bottom_hole_pressure
                FROM subsurface.dst
                WHERE wellbore_id IN ({placeholders}){depth_filter}
                  AND (final_shut_in_pressure > 0 OR final_flow_pressure > 0 OR bottom_hole_pressure > 0)
                ORDER BY wellbore_id, from_depth_m""",
            params,
        )

        results = []
        for row in cur.fetchall():
            wb_id = row[0]
            well_id, dataset, dist = wb_map.get(wb_id, ("", "", None))
            results.append(PressureEvidence(
                wellbore_id=wb_id,
                well_id=well_id,
                dataset=dataset,
                from_depth_m=row[1],
                to_depth_m=row[2],
                shut_in_pressure=row[3],
                flow_pressure=row[4],
                bottom_hole_pressure=row[5],
                distance_km=dist,
            ))
        return results
    finally:
        if own_conn:
            conn.close()


def get_mud_weight_for_nearby_wells(
    nearby_wellbore_ids: List[Tuple[int, str, str, Optional[float]]],
    target_depth_m: Optional[float] = None,
    depth_tolerance_m: float = 300.0,
    conn=None,
) -> List[MudWeightEvidence]:
    """Fetch mud weight data for nearby wells near a target depth."""
    if not nearby_wellbore_ids:
        return []

    own_conn = conn is None
    if own_conn:
        conn = psycopg2.connect(**DB_CONFIG)
    try:
        cur = conn.cursor()
        wb_ids = [n[0] for n in nearby_wellbore_ids]
        wb_map = {n[0]: (n[1], n[2], n[3]) for n in nearby_wellbore_ids}

        placeholders = ",".join(["%s"] * len(wb_ids))
        params: list = list(wb_ids)

        depth_filter = ""
        if target_depth_m is not None:
            depth_filter = " AND md_m >= %s AND md_m <= %s"
            params.extend([target_depth_m - depth_tolerance_m, target_depth_m + depth_tolerance_m])

        cur.execute(
            f"""SELECT wellbore_id, md_m, mud_weight, mud_type
                FROM subsurface.mud
                WHERE wellbore_id IN ({placeholders}){depth_filter}
                  AND mud_weight IS NOT NULL AND mud_weight > 0
                ORDER BY wellbore_id, md_m""",
            params,
        )

        results = []
        for row in cur.fetchall():
            wb_id = row[0]
            well_id, dataset, dist = wb_map.get(wb_id, ("", "", None))
            results.append(MudWeightEvidence(
                wellbore_id=wb_id,
                well_id=well_id,
                dataset=dataset,
                depth_m=row[1],
                mud_weight=row[2],
                mud_type=row[3],
                distance_km=dist,
            ))
        return results
    finally:
        if own_conn:
            conn.close()


def get_caliper_evidence_for_wells(
    well_ids: List[Tuple[str, str]],
    target_depth_m: Optional[float] = None,
    depth_tolerance_m: float = 200.0,
) -> List[CaliperEvidence]:
    """Extract caliper washout indicators from unified features for wells near a depth."""
    try:
        import pandas as pd
        df = pd.read_parquet("data/unified/unified_features.parquet")
    except Exception:
        return []

    results = []
    for well_id, dataset in well_ids:
        mask = (df["well_id"] == well_id) & (df["dataset"] == dataset)
        if target_depth_m is not None:
            mask = mask & (
                df["depth_start_m"] <= target_depth_m + depth_tolerance_m
            ) & (
                df["depth_end_m"] >= target_depth_m - depth_tolerance_m
            )

        subset = df[mask]
        for _, row in subset.iterrows():
            if pd.isna(row.get("caliper_mean")) or pd.isna(row.get("caliper_present")) or not row["caliper_present"]:
                continue

            bit_size_mean = row.get("bit_size_mean") if not pd.isna(row.get("bit_size_mean")) else None
            washout = None
            if bit_size_mean and bit_size_mean > 0:
                washout = round(row["caliper_mean"] / bit_size_mean, 3)

            results.append(CaliperEvidence(
                well_id=well_id,
                dataset=dataset,
                depth_start_m=row["depth_start_m"],
                depth_end_m=row["depth_end_m"],
                caliper_mean=round(row["caliper_mean"], 2),
                caliper_max=round(row["caliper_max"], 2),
                bit_size_mean=round(bit_size_mean, 2) if bit_size_mean else None,
                washout_ratio=washout,
            ))

    return results


def gather_well_evidence(
    well_id: str,
    dataset: str,
    current_depth_m: Optional[float] = None,
    radius_km: float = 50.0,
    conn=None,
) -> WellEvidenceSummary:
    """Gather all additional evidence sources for a well context."""
    own_conn = conn is None
    if own_conn:
        conn = psycopg2.connect(**DB_CONFIG)

    try:
        from nearby.search import find_nearby_wells, get_well_location

        summary = WellEvidenceSummary()

        location = get_well_location(well_id, dataset, conn=conn)
        if not location or not location.has_coordinates:
            summary.evidence_summary.append("No coordinates available — cannot search nearby wells for pressure/mud data.")
            return summary

        try:
            nearby = find_nearby_wells(well_id, dataset, radius_km=radius_km, limit=30, conn=conn)
        except ValueError:
            summary.evidence_summary.append("Well has no coordinates for nearby search.")
            return summary

        nearby_wb_ids = []
        nearby_well_ids = []
        for n in nearby:
            if n.sodir_wellbore_id:
                nearby_wb_ids.append((n.sodir_wellbore_id, n.well_id, n.dataset, n.distance_km))
            nearby_well_ids.append((n.well_id, n.dataset))

        # Include own well
        if location.sodir_wellbore_id:
            nearby_wb_ids.insert(0, (location.sodir_wellbore_id, well_id, dataset, 0.0))
        nearby_well_ids.insert(0, (well_id, dataset))

        # DST pressure
        summary.pressure_evidence = get_dst_pressure_for_nearby_wells(
            nearby_wb_ids, current_depth_m, conn=conn,
        )
        if summary.pressure_evidence:
            pressures = [p.bottom_hole_pressure for p in summary.pressure_evidence if p.bottom_hole_pressure > 0]
            if pressures:
                summary.max_pressure_psi = max(pressures)
                summary.evidence_summary.append(
                    f"{len(summary.pressure_evidence)} DST pressure reading(s) from nearby wells. "
                    f"Max BHP: {summary.max_pressure_psi:.1f}."
                )

        # Mud weight
        summary.mud_weight_evidence = get_mud_weight_for_nearby_wells(
            nearby_wb_ids, current_depth_m, conn=conn,
        )
        if summary.mud_weight_evidence:
            weights = [m.mud_weight for m in summary.mud_weight_evidence]
            summary.avg_mud_weight = sum(weights) / len(weights)
            summary.evidence_summary.append(
                f"{len(summary.mud_weight_evidence)} mud weight record(s) from nearby wells. "
                f"Avg weight: {summary.avg_mud_weight:.2f}."
            )

        # Caliper
        summary.caliper_evidence = get_caliper_evidence_for_wells(
            nearby_well_ids, current_depth_m,
        )
        if summary.caliper_evidence:
            washouts = [c.washout_ratio for c in summary.caliper_evidence if c.washout_ratio]
            if washouts:
                summary.max_washout_ratio = max(washouts)
                high_washout = [w for w in washouts if w > 1.15]
                if high_washout:
                    summary.evidence_summary.append(
                        f"{len(high_washout)} window(s) show caliper washout >15% "
                        f"(max ratio: {summary.max_washout_ratio:.2f})."
                    )

        if not summary.evidence_summary:
            summary.evidence_summary.append("No additional pressure, mud weight, or caliper data found for nearby wells at this depth.")

        return summary

    finally:
        if own_conn:
            conn.close()
