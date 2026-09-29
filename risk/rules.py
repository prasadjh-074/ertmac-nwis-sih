"""Deterministic rule engine for drilling risk intelligence.

Each rule evaluates correlated historical events against specific
conditions and produces explainable evidence when triggered.
"""

from __future__ import annotations

from typing import List, Optional

from events.models import CorrelatedEvent, EventType
from .models import RiskLevel, RuleResult, RuleType


def _event_summary(c: CorrelatedEvent) -> dict:
    return {
        "well_id": c.source_well_id,
        "dataset": c.source_dataset,
        "event_type": c.event.event_type.value,
        "severity": c.event.severity.value,
        "depth_m": c.event.depth_start_m,
        "formation": c.event.formation,
        "distance_km": c.distance_km,
    }


def rule_formation_history_warning(
    correlated_events: List[CorrelatedEvent],
    current_formation: Optional[str] = None,
) -> RuleResult:
    """Triggers when multiple historical events share the current formation."""
    if not current_formation:
        return RuleResult(rule_type=RuleType.FORMATION_HISTORY_WARNING, triggered=False)

    matches = [c for c in correlated_events if c.formation_match]
    if len(matches) < 2:
        return RuleResult(rule_type=RuleType.FORMATION_HISTORY_WARNING, triggered=False)

    types = {c.event.event_type.value for c in matches}
    severity = RiskLevel.HIGH if len(matches) >= 4 else RiskLevel.MEDIUM

    return RuleResult(
        rule_type=RuleType.FORMATION_HISTORY_WARNING,
        triggered=True,
        severity=severity,
        evidence=[
            f"{len(matches)} historical event(s) recorded in the {current_formation} formation.",
            f"Event types: {', '.join(sorted(types))}.",
        ],
        contributing_events=[_event_summary(c) for c in matches[:5]],
        details={"formation": current_formation, "event_count": len(matches)},
    )


def rule_nearby_stuck_pipe(
    correlated_events: List[CorrelatedEvent],
) -> RuleResult:
    """Triggers when nearby wells have stuck pipe history."""
    stuck = [
        c for c in correlated_events
        if c.event.event_type == EventType.STUCK_PIPE
        and not c.relevance_factors.get("own_well")
    ]
    if not stuck:
        return RuleResult(rule_type=RuleType.NEARBY_STUCK_PIPE_HISTORY, triggered=False)

    wells = {(c.source_well_id, c.source_dataset) for c in stuck}
    severity = RiskLevel.HIGH if len(wells) >= 3 else RiskLevel.MEDIUM

    return RuleResult(
        rule_type=RuleType.NEARBY_STUCK_PIPE_HISTORY,
        triggered=True,
        severity=severity,
        evidence=[
            f"{len(stuck)} stuck pipe event(s) in {len(wells)} nearby well(s).",
        ],
        contributing_events=[_event_summary(c) for c in stuck[:5]],
        details={"event_count": len(stuck), "well_count": len(wells)},
    )


def rule_nearby_mud_loss(
    correlated_events: List[CorrelatedEvent],
) -> RuleResult:
    """Triggers when nearby wells have mud loss history."""
    losses = [
        c for c in correlated_events
        if c.event.event_type == EventType.MUD_LOSS
        and not c.relevance_factors.get("own_well")
    ]
    if not losses:
        return RuleResult(rule_type=RuleType.NEARBY_MUD_LOSS_HISTORY, triggered=False)

    wells = {(c.source_well_id, c.source_dataset) for c in losses}
    depth_overlap = [c for c in losses if c.depth_overlap]
    severity = RiskLevel.HIGH if len(wells) >= 3 or len(depth_overlap) >= 2 else RiskLevel.MEDIUM

    evidence_lines = [f"{len(losses)} mud loss event(s) in {len(wells)} nearby well(s)."]
    if depth_overlap:
        evidence_lines.append(f"{len(depth_overlap)} overlap the current depth interval.")

    return RuleResult(
        rule_type=RuleType.NEARBY_MUD_LOSS_HISTORY,
        triggered=True,
        severity=severity,
        evidence=evidence_lines,
        contributing_events=[_event_summary(c) for c in losses[:5]],
        details={"event_count": len(losses), "well_count": len(wells), "depth_overlaps": len(depth_overlap)},
    )


def rule_kick_history_warning(
    correlated_events: List[CorrelatedEvent],
) -> RuleResult:
    """Triggers when any correlated kick or overpressure events exist."""
    kicks = [
        c for c in correlated_events
        if c.event.event_type in (EventType.KICK, EventType.OVERPRESSURE)
    ]
    if not kicks:
        return RuleResult(rule_type=RuleType.KICK_HISTORY_WARNING, triggered=False)

    severity = RiskLevel.HIGH
    return RuleResult(
        rule_type=RuleType.KICK_HISTORY_WARNING,
        triggered=True,
        severity=severity,
        evidence=[
            f"{len(kicks)} kick/overpressure event(s) in correlated wells.",
            "Well control events warrant heightened monitoring regardless of count.",
        ],
        contributing_events=[_event_summary(c) for c in kicks[:5]],
        details={"event_count": len(kicks)},
    )


def rule_torque_history_warning(
    correlated_events: List[CorrelatedEvent],
) -> RuleResult:
    """Triggers when correlated torque spike events exist."""
    torque = [
        c for c in correlated_events
        if c.event.event_type == EventType.TORQUE_SPIKE
    ]
    if not torque:
        return RuleResult(rule_type=RuleType.TORQUE_HISTORY_WARNING, triggered=False)

    return RuleResult(
        rule_type=RuleType.TORQUE_HISTORY_WARNING,
        triggered=True,
        severity=RiskLevel.MEDIUM,
        evidence=[f"{len(torque)} torque spike event(s) in correlated wells."],
        contributing_events=[_event_summary(c) for c in torque[:5]],
        details={"event_count": len(torque)},
    )


def rule_cementing_history_warning(
    correlated_events: List[CorrelatedEvent],
) -> RuleResult:
    """Triggers when correlated cementing issue events exist."""
    cement = [
        c for c in correlated_events
        if c.event.event_type == EventType.CEMENTING_ISSUE
    ]
    if not cement:
        return RuleResult(rule_type=RuleType.CEMENTING_HISTORY_WARNING, triggered=False)

    return RuleResult(
        rule_type=RuleType.CEMENTING_HISTORY_WARNING,
        triggered=True,
        severity=RiskLevel.MEDIUM,
        evidence=[f"{len(cement)} cementing issue event(s) in correlated wells."],
        contributing_events=[_event_summary(c) for c in cement[:5]],
        details={"event_count": len(cement)},
    )


def rule_high_risk_event_cluster(
    correlated_events: List[CorrelatedEvent],
) -> RuleResult:
    """Triggers when multiple different high-severity event types cluster
    in nearby wells, indicating a systematically hazardous zone."""
    high_sev = [
        c for c in correlated_events
        if c.event.severity.value in ("high", "critical")
        and not c.relevance_factors.get("own_well")
    ]
    if len(high_sev) < 3:
        return RuleResult(rule_type=RuleType.HIGH_RISK_EVENT_CLUSTER, triggered=False)

    distinct_types = {c.event.event_type.value for c in high_sev}
    if len(distinct_types) < 2:
        return RuleResult(rule_type=RuleType.HIGH_RISK_EVENT_CLUSTER, triggered=False)

    return RuleResult(
        rule_type=RuleType.HIGH_RISK_EVENT_CLUSTER,
        triggered=True,
        severity=RiskLevel.HIGH,
        evidence=[
            f"{len(high_sev)} high/critical severity event(s) of {len(distinct_types)} "
            f"distinct type(s) in nearby wells.",
            f"Event types: {', '.join(sorted(distinct_types))}.",
            "Multiple co-occurring hazard types suggest a systematically challenging zone.",
        ],
        contributing_events=[_event_summary(c) for c in high_sev[:5]],
        details={
            "event_count": len(high_sev),
            "distinct_types": sorted(distinct_types),
        },
    )


def evaluate_all_rules(
    correlated_events: List[CorrelatedEvent],
    current_formation: Optional[str] = None,
) -> List[RuleResult]:
    """Run all deterministic rules and return results (including non-triggered)."""
    return [
        rule_formation_history_warning(correlated_events, current_formation),
        rule_nearby_stuck_pipe(correlated_events),
        rule_nearby_mud_loss(correlated_events),
        rule_kick_history_warning(correlated_events),
        rule_torque_history_warning(correlated_events),
        rule_cementing_history_warning(correlated_events),
        rule_high_risk_event_cluster(correlated_events),
    ]
