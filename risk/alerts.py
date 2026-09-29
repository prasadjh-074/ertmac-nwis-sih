"""Alert generation from risk assessments and rule evaluations.

Generates evidence-backed alerts with actionable recommendations.
Recommendations are decision support only — this system does not
claim autonomous drilling control.
"""

from __future__ import annotations

from typing import Dict, List, Optional

from .models import (
    Alert,
    AlertSeverity,
    RiskAssessment,
    RiskLevel,
    RiskType,
    RuleResult,
    RuleType,
)

_RISK_LEVEL_TO_ALERT_SEVERITY: Dict[RiskLevel, AlertSeverity] = {
    RiskLevel.HIGH: AlertSeverity.HIGH,
    RiskLevel.MEDIUM: AlertSeverity.WARNING,
    RiskLevel.LOW: AlertSeverity.INFO,
    RiskLevel.UNKNOWN: AlertSeverity.INFO,
}

_RISK_RECOMMENDATIONS: Dict[RiskType, Dict[RiskLevel, str]] = {
    RiskType.MUD_LOSS_RISK: {
        RiskLevel.HIGH: "Increase monitoring of returns and mud-loss indicators. Consider pre-treating mud system with LCM before entering the interval.",
        RiskLevel.MEDIUM: "Monitor returns closely. Have lost-circulation material on standby.",
        RiskLevel.LOW: "Standard monitoring of mud returns.",
    },
    RiskType.STUCK_PIPE_RISK: {
        RiskLevel.HIGH: "Minimize static time. Maintain hole cleaning practices. Consider wiper trips before connections.",
        RiskLevel.MEDIUM: "Monitor drag and overpull trends. Ensure adequate hole cleaning.",
        RiskLevel.LOW: "Standard stuck-pipe prevention practices.",
    },
    RiskType.KICK_OVERPRESSURE_RISK: {
        RiskLevel.HIGH: "Verify well control equipment readiness. Monitor pit volumes and flow rates continuously. Review kill sheet.",
        RiskLevel.MEDIUM: "Heighten well control monitoring. Review expected pore pressure profile.",
        RiskLevel.LOW: "Standard well control monitoring.",
    },
    RiskType.TORQUE_SPIKE_RISK: {
        RiskLevel.HIGH: "Monitor torque and drag trends closely. Consider BHA design review for the section.",
        RiskLevel.MEDIUM: "Track torque trends for deviations from baseline.",
        RiskLevel.LOW: "Standard torque monitoring.",
    },
    RiskType.CEMENTING_RISK: {
        RiskLevel.HIGH: "Review cement program for the interval. Consider contingency cement volumes and remedial options.",
        RiskLevel.MEDIUM: "Review cement design parameters against offset well experience.",
        RiskLevel.LOW: "Standard cementing procedures.",
    },
}

_RULE_RECOMMENDATIONS: Dict[RuleType, str] = {
    RuleType.FORMATION_HISTORY_WARNING: "Review offset well reports for this formation. Multiple event types suggest formation-specific challenges.",
    RuleType.NEARBY_STUCK_PIPE_HISTORY: "Review stuck-pipe mitigation plans. Offset wells experienced stuck pipe in this area.",
    RuleType.NEARBY_MUD_LOSS_HISTORY: "Prepare lost-circulation material. Offset wells experienced mud losses in this area.",
    RuleType.KICK_HISTORY_WARNING: "Verify BOP function test is current. Review kick indicators and response procedures.",
    RuleType.TORQUE_HISTORY_WARNING: "Monitor torque trends. Offset wells experienced torque issues.",
    RuleType.CEMENTING_HISTORY_WARNING: "Review cementing program against offset well experience.",
    RuleType.HIGH_RISK_EVENT_CLUSTER: "Multiple hazard types concentrated in nearby wells suggest a systematically challenging zone. Consider comprehensive risk review before proceeding.",
}


def generate_alerts_from_risks(
    risk_assessments: List[RiskAssessment],
    well_id: str = "",
    dataset: str = "",
) -> List[Alert]:
    """Generate alerts from risk assessments that exceed LOW level."""
    alerts = []
    alert_counter = 0

    for ra in risk_assessments:
        if ra.level == RiskLevel.LOW:
            continue

        alert_counter += 1
        severity = _RISK_LEVEL_TO_ALERT_SEVERITY.get(ra.level, AlertSeverity.INFO)
        recommendations = _RISK_RECOMMENDATIONS.get(ra.risk_type, {})
        recommended = recommendations.get(ra.level, "Review historical data for this risk type.")

        title = f"{ra.level.value.upper()} {ra.risk_type.value.upper().replace('_', ' ')}"

        explanation_parts = list(ra.evidence)
        if ra.contributing_features.get("event_count"):
            explanation_parts.append(
                f"Based on {ra.contributing_features['event_count']} historical event(s) "
                f"across {ra.contributing_features.get('distinct_wells', '?')} well(s)."
            )

        alerts.append(Alert(
            alert_id=alert_counter,
            alert_type=ra.risk_type.value,
            severity=severity,
            title=title,
            explanation=" ".join(explanation_parts),
            evidence=ra.evidence,
            recommended_action=recommended,
            provenance=[ra.model_or_rule_source],
            context={
                "well_id": well_id,
                "dataset": dataset,
                "risk_score": ra.score,
                "risk_level": ra.level.value,
                "confidence": ra.confidence,
                "methodology": ra.methodology.value,
            },
        ))

    return alerts


def generate_alerts_from_rules(
    rule_results: List[RuleResult],
    well_id: str = "",
    dataset: str = "",
    alert_id_start: int = 100,
) -> List[Alert]:
    """Generate alerts from triggered rules."""
    alerts = []
    counter = alert_id_start

    for rr in rule_results:
        if not rr.triggered:
            continue

        counter += 1
        severity_map = {
            RiskLevel.HIGH: AlertSeverity.HIGH,
            RiskLevel.MEDIUM: AlertSeverity.WARNING,
            RiskLevel.LOW: AlertSeverity.INFO,
            RiskLevel.UNKNOWN: AlertSeverity.INFO,
        }
        severity = severity_map.get(rr.severity, AlertSeverity.INFO)
        recommended = _RULE_RECOMMENDATIONS.get(rr.rule_type, "Review offset well data.")

        title = rr.rule_type.value.upper().replace("_", " ")

        alerts.append(Alert(
            alert_id=counter,
            alert_type=rr.rule_type.value,
            severity=severity,
            title=title,
            explanation=" ".join(rr.evidence),
            evidence=rr.evidence,
            recommended_action=recommended,
            provenance=["deterministic_rule"],
            context={
                "well_id": well_id,
                "dataset": dataset,
                "rule_type": rr.rule_type.value,
                "rule_severity": rr.severity.value,
                "details": rr.details,
            },
        ))

    return alerts


def generate_all_alerts(
    risk_assessments: List[RiskAssessment],
    rule_results: List[RuleResult],
    well_id: str = "",
    dataset: str = "",
) -> List[Alert]:
    """Generate all alerts from both risk assessments and rule results.

    Returns alerts sorted by severity (critical first).
    """
    risk_alerts = generate_alerts_from_risks(risk_assessments, well_id, dataset)
    rule_alerts = generate_alerts_from_rules(rule_results, well_id, dataset)

    all_alerts = risk_alerts + rule_alerts
    severity_order = {
        AlertSeverity.CRITICAL: 0,
        AlertSeverity.HIGH: 1,
        AlertSeverity.WARNING: 2,
        AlertSeverity.INFO: 3,
    }
    all_alerts.sort(key=lambda a: severity_order.get(a.severity, 4))
    return all_alerts
