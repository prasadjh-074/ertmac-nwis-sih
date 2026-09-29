"""Evidence-based historical risk scoring.

Computes risk scores from multiple evidence sources:
- Historical drilling event frequency, proximity, depth/formation overlap
- DST pressure data from nearby wells
- Mud weight data from nearby wells
- Caliper/washout indicators from petrophysical logs

All scores are heuristic evidence indicators, NOT calibrated
probabilities.  The system explicitly documents this distinction.
"""

from __future__ import annotations

from typing import Dict, List, Optional

from events.models import CorrelatedEvent, EventType
from .models import RiskAssessment, RiskLevel, RiskType

_RISK_TO_EVENT_TYPES: Dict[RiskType, List[EventType]] = {
    RiskType.MUD_LOSS_RISK: [EventType.MUD_LOSS],
    RiskType.STUCK_PIPE_RISK: [EventType.STUCK_PIPE],
    RiskType.KICK_OVERPRESSURE_RISK: [EventType.KICK, EventType.OVERPRESSURE],
    RiskType.TORQUE_SPIKE_RISK: [EventType.TORQUE_SPIKE],
    RiskType.CEMENTING_RISK: [EventType.CEMENTING_ISSUE],
}

_SEVERITY_WEIGHTS = {
    "low": 0.25,
    "medium": 0.5,
    "high": 0.75,
    "critical": 1.0,
    "unknown": 0.3,
}

_LEVEL_THRESHOLDS = {
    "high": 0.6,
    "medium": 0.3,
}


def _score_to_level(score: float) -> RiskLevel:
    if score >= _LEVEL_THRESHOLDS["high"]:
        return RiskLevel.HIGH
    if score >= _LEVEL_THRESHOLDS["medium"]:
        return RiskLevel.MEDIUM
    return RiskLevel.LOW


def assess_single_risk(
    risk_type: RiskType,
    correlated_events: List[CorrelatedEvent],
    current_depth_m: Optional[float] = None,
    current_formation: Optional[str] = None,
    well_evidence=None,
) -> RiskAssessment:
    """Assess a single risk type from correlated historical events
    and optional additional evidence (DST pressure, mud weight, caliper).

    The score is built from transparent components:
    1. event_frequency: how many relevant events exist (capped)
    2. proximity_factor: how close the source wells are
    3. depth_factor: depth overlap with current drilling position
    4. formation_factor: formation match with current formation
    5. supplementary_factor: DST/mud/caliper evidence (risk-type specific)
    """
    relevant_event_types = _RISK_TO_EVENT_TYPES[risk_type]
    relevant = [
        c for c in correlated_events
        if c.event.event_type in relevant_event_types
    ]

    evidence_lines: List[str] = []
    features: Dict = {"event_count": 0}
    supplementary_score = 0.0
    supplementary_details: Dict = {}

    if well_evidence:
        sup = _compute_supplementary_score(risk_type, well_evidence)
        supplementary_score = sup["score"]
        supplementary_details = sup
        evidence_lines.extend(sup.get("evidence", []))

    if not relevant and supplementary_score == 0.0:
        return RiskAssessment(
            risk_type=risk_type,
            score=0.0,
            level=RiskLevel.LOW,
            confidence=0.0,
            evidence=["No historical events of this type found in nearby or correlated wells."]
                + (well_evidence.evidence_summary if well_evidence else []),
            contributing_features={"event_count": 0},
            model_or_rule_source="evidence_rule_based",
            limitations=[
                "Score is a heuristic evidence indicator, not a calibrated probability.",
                "No relevant historical events found — risk cannot be assessed from evidence.",
            ],
        )

    event_count = len(relevant)
    distinct_wells = len({(c.source_well_id, c.source_dataset) for c in relevant}) if relevant else 0

    frequency_score = min(1.0, event_count / 10.0)

    proximity_scores = []
    for c in relevant:
        if c.distance_km is not None:
            proximity_scores.append(max(0.0, 1.0 - c.distance_km / 50.0))
        elif c.relevance_factors.get("own_well"):
            proximity_scores.append(1.0)
    proximity_factor = (sum(proximity_scores) / len(proximity_scores)) if proximity_scores else 0.0

    depth_overlap_count = sum(1 for c in relevant if c.depth_overlap)
    depth_factor = min(1.0, depth_overlap_count / max(1, event_count)) if relevant else 0.0

    formation_match_count = sum(1 for c in relevant if c.formation_match)
    formation_factor = min(1.0, formation_match_count / max(1, event_count)) if relevant else 0.0

    severity_scores = [
        _SEVERITY_WEIGHTS.get(c.event.severity.value, 0.3) for c in relevant
    ]
    avg_severity = (sum(severity_scores) / len(severity_scores)) if severity_scores else 0.0

    # Composite score — weighted sum with supplementary evidence
    if supplementary_score > 0:
        raw_score = (
            0.25 * frequency_score
            + 0.20 * proximity_factor
            + 0.15 * depth_factor
            + 0.10 * formation_factor
            + 0.10 * avg_severity
            + 0.20 * supplementary_score
        )
    else:
        raw_score = (
            0.30 * frequency_score
            + 0.25 * proximity_factor
            + 0.20 * depth_factor
            + 0.15 * formation_factor
            + 0.10 * avg_severity
        )
    score = min(1.0, raw_score)

    confidence = min(1.0, 0.2 + 0.1 * event_count + 0.1 * distinct_wells)
    if supplementary_score > 0:
        confidence = min(1.0, confidence + 0.15)

    if event_count > 0:
        evidence_lines.insert(0,
            f"{event_count} historical {relevant_event_types[0].value} event(s) "
            f"found across {distinct_wells} well(s).",
        )
    if depth_overlap_count > 0:
        evidence_lines.append(f"{depth_overlap_count} event(s) overlap current depth interval.")
    if formation_match_count > 0:
        evidence_lines.append(f"{formation_match_count} event(s) match current formation.")

    historical = []
    for c in relevant[:5]:
        historical.append({
            "well_id": c.source_well_id,
            "dataset": c.source_dataset,
            "event_type": c.event.event_type.value,
            "severity": c.event.severity.value,
            "depth_m": c.event.depth_start_m,
            "formation": c.event.formation,
            "distance_km": c.distance_km,
            "depth_overlap": c.depth_overlap,
            "formation_match": c.formation_match,
        })

    features = {
        "event_count": event_count,
        "distinct_wells": distinct_wells,
        "frequency_score": round(frequency_score, 3),
        "proximity_factor": round(proximity_factor, 3),
        "depth_factor": round(depth_factor, 3),
        "formation_factor": round(formation_factor, 3),
        "avg_severity": round(avg_severity, 3),
        "supplementary_score": round(supplementary_score, 3),
    }
    features.update(supplementary_details)

    return RiskAssessment(
        risk_type=risk_type,
        score=round(score, 4),
        level=_score_to_level(score),
        confidence=round(confidence, 3),
        evidence=evidence_lines,
        contributing_features=features,
        historical_events=historical,
        model_or_rule_source="evidence_rule_based",
    )


def _compute_supplementary_score(risk_type: RiskType, well_evidence) -> Dict:
    """Compute risk-type-specific supplementary score from DST/mud/caliper."""
    result: Dict = {"score": 0.0, "evidence": []}

    if risk_type == RiskType.KICK_OVERPRESSURE_RISK:
        if well_evidence.pressure_evidence:
            pressures = [p.bottom_hole_pressure for p in well_evidence.pressure_evidence if p.bottom_hole_pressure > 0]
            if pressures:
                max_p = max(pressures)
                result["max_bhp"] = round(max_p, 1)
                result["dst_count"] = len(well_evidence.pressure_evidence)
                # High BHP relative to depth suggests overpressure
                result["score"] = min(1.0, len(pressures) / 5.0) * 0.5
                result["evidence"].append(
                    f"{len(pressures)} DST reading(s) with BHP data. Max BHP: {max_p:.1f}."
                )

        if well_evidence.mud_weight_evidence:
            weights = [m.mud_weight for m in well_evidence.mud_weight_evidence]
            avg_w = sum(weights) / len(weights)
            max_w = max(weights)
            result["avg_mud_weight"] = round(avg_w, 2)
            result["max_mud_weight"] = round(max_w, 2)
            # High mud weight (>1.5 SG / 12.5 ppg) indicates pressure challenges
            if max_w > 1.5:
                result["score"] = min(1.0, result["score"] + 0.3)
                result["evidence"].append(
                    f"Nearby wells used elevated mud weight (max: {max_w:.2f}) suggesting pressure management challenges."
                )

    elif risk_type == RiskType.MUD_LOSS_RISK:
        if well_evidence.mud_weight_evidence:
            weights = [m.mud_weight for m in well_evidence.mud_weight_evidence]
            max_w = max(weights)
            result["max_mud_weight"] = round(max_w, 2)
            if max_w > 1.4:
                result["score"] = min(1.0, 0.2)
                result["evidence"].append(
                    f"Nearby wells used mud weight up to {max_w:.2f} — higher weights increase mud loss risk in fractured zones."
                )

    elif risk_type == RiskType.STUCK_PIPE_RISK:
        if well_evidence.caliper_evidence:
            washouts = [c.washout_ratio for c in well_evidence.caliper_evidence if c.washout_ratio]
            if washouts:
                high_washout = [w for w in washouts if w > 1.15]
                result["washout_count"] = len(high_washout)
                result["max_washout_ratio"] = round(max(washouts), 3)
                if high_washout:
                    result["score"] = min(1.0, len(high_washout) / 5.0) * 0.5
                    result["evidence"].append(
                        f"{len(high_washout)} depth window(s) in nearby wells show caliper washout >15% "
                        f"(max ratio: {max(washouts):.2f}), indicating hole instability and stuck pipe risk."
                    )

        if well_evidence.mud_weight_evidence:
            weights = [m.mud_weight for m in well_evidence.mud_weight_evidence]
            result["avg_mud_weight_stuck"] = round(sum(weights) / len(weights), 2)

    elif risk_type == RiskType.CEMENTING_RISK:
        if well_evidence.caliper_evidence:
            washouts = [c.washout_ratio for c in well_evidence.caliper_evidence if c.washout_ratio and c.washout_ratio > 1.2]
            if washouts:
                result["severe_washout_count"] = len(washouts)
                result["score"] = min(1.0, len(washouts) / 3.0) * 0.3
                result["evidence"].append(
                    f"{len(washouts)} window(s) show severe caliper washout >20%, "
                    f"which complicates cementing operations."
                )

    return result


def assess_all_risks(
    correlated_events: List[CorrelatedEvent],
    current_depth_m: Optional[float] = None,
    current_formation: Optional[str] = None,
    well_evidence=None,
) -> List[RiskAssessment]:
    """Assess all 5 risk types from correlated historical events
    and optional additional evidence sources."""
    return [
        assess_single_risk(rt, correlated_events, current_depth_m, current_formation, well_evidence)
        for rt in RiskType
    ]
