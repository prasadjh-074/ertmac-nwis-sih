"""Risk intelligence endpoints.

  GET /risk/assess   — evidence-based risk assessments for a well
  GET /risk/alerts   — evidence-backed alerts derived from those
                        assessments and the deterministic rule engine

Risk scores are HEURISTIC EVIDENCE INDICATORS, not calibrated
probabilities.  Every response carries the ``methodology`` and
``limitations`` fields from ``risk/models.py`` so callers don't
misinterpret the numbers.

The system deliberately uses evidence/rule-based scoring rather than
an ML model because the available labeled data (31 events across 20
wells) is insufficient — see ``docs/risk_intelligence.md``.
"""

from __future__ import annotations

import logging
from dataclasses import asdict
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from events.correlation import correlate_historical_events
from risk.alerts import generate_all_alerts
from risk.rules import evaluate_all_rules
from risk.scoring import assess_all_risks

from ..deps import get_conn

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/risk", tags=["risk"])


class RiskAssessmentResponse(BaseModel):
    risk_type: str
    score: float
    level: str
    confidence: float
    evidence: List[str] = Field(default_factory=list)
    contributing_features: Dict[str, Any] = Field(default_factory=dict)
    historical_events: List[Dict[str, Any]] = Field(default_factory=list)
    methodology: str
    limitations: List[str] = Field(default_factory=list)
    model_or_rule_source: str


class RuleResultResponse(BaseModel):
    rule_type: str
    triggered: bool
    severity: str
    evidence: List[str] = Field(default_factory=list)
    contributing_events: List[Dict[str, Any]] = Field(default_factory=list)
    details: Dict[str, Any] = Field(default_factory=dict)


class AlertResponse(BaseModel):
    alert_id: Optional[int] = None
    alert_type: str
    severity: str
    title: str
    explanation: str
    evidence: List[str] = Field(default_factory=list)
    recommended_action: str
    provenance: List[str] = Field(default_factory=list)
    context: Dict[str, Any] = Field(default_factory=dict)


class RiskAssessResponse(BaseModel):
    well_id: str
    dataset: str
    current_depth_m: Optional[float] = None
    current_formation: Optional[str] = None
    correlated_event_count: int
    assessments: List[RiskAssessmentResponse]
    rules: List[RuleResultResponse]


class AlertListResponse(BaseModel):
    well_id: str
    dataset: str
    count: int
    alerts: List[AlertResponse]


def _assessment_to_response(ra) -> RiskAssessmentResponse:
    return RiskAssessmentResponse(
        risk_type=ra.risk_type.value,
        score=ra.score,
        level=ra.level.value,
        confidence=ra.confidence,
        evidence=list(ra.evidence),
        contributing_features=dict(ra.contributing_features),
        historical_events=list(ra.historical_events),
        methodology=ra.methodology.value,
        limitations=list(ra.limitations),
        model_or_rule_source=ra.model_or_rule_source,
    )


def _rule_to_response(rr) -> RuleResultResponse:
    return RuleResultResponse(
        rule_type=rr.rule_type.value,
        triggered=rr.triggered,
        severity=rr.severity.value,
        evidence=list(rr.evidence),
        contributing_events=list(rr.contributing_events),
        details=dict(rr.details),
    )


def _alert_to_response(a) -> AlertResponse:
    return AlertResponse(
        alert_id=a.alert_id,
        alert_type=a.alert_type,
        severity=a.severity.value,
        title=a.title,
        explanation=a.explanation,
        evidence=list(a.evidence),
        recommended_action=a.recommended_action,
        provenance=list(a.provenance),
        context=dict(a.context),
    )


def _gather_well_evidence_safe(well_id: str, dataset: str, current_depth_m, conn):
    """Best-effort call to risk.evidence_sources.gather_well_evidence.

    Failures here are non-fatal — the assessment falls back to
    events-only scoring, which is still meaningful.  We log the reason
    so operators can see why the supplementary signal was skipped.
    """
    try:
        from risk.evidence_sources import gather_well_evidence

        return gather_well_evidence(
            well_id, dataset, current_depth_m=current_depth_m, conn=conn,
        )
    except Exception as exc:
        logger.info("gather_well_evidence unavailable for %s:%s: %s",
                    dataset, well_id, exc)
        return None


@router.get("/assess", response_model=RiskAssessResponse)
def assess_risk(
    dataset: str = Query(...),
    well_id: str = Query(...),
    current_depth_m: Optional[float] = Query(None, ge=0),
    current_formation: Optional[str] = Query(None, max_length=100),
    radius_km: float = Query(50.0, gt=0, le=500),
    limit: int = Query(50, ge=1, le=200),
    conn=Depends(get_conn),
):
    """Compute risk assessments + deterministic rule evaluations for a well.

    Returns all 5 risk types (mud_loss, stuck_pipe, kick_overpressure,
    torque_spike, cementing) — a LOW score is meaningful ("no
    supporting evidence found") and is always returned, never filtered.
    """
    try:
        correlated = correlate_historical_events(
            well_id=well_id, dataset=dataset,
            current_depth_m=current_depth_m,
            current_formation=current_formation,
            radius_km=radius_km, limit=limit, conn=conn,
        )
    except Exception as exc:
        logger.exception("event correlation failed: %s", exc)
        raise HTTPException(status_code=500, detail="event correlation failed")

    well_evidence = _gather_well_evidence_safe(well_id, dataset, current_depth_m, conn)

    assessments = assess_all_risks(
        correlated_events=correlated,
        current_depth_m=current_depth_m,
        current_formation=current_formation,
        well_evidence=well_evidence,
    )
    rules = evaluate_all_rules(correlated, current_formation=current_formation)

    return RiskAssessResponse(
        well_id=well_id, dataset=dataset,
        current_depth_m=current_depth_m,
        current_formation=current_formation,
        correlated_event_count=len(correlated),
        assessments=[_assessment_to_response(a) for a in assessments],
        rules=[_rule_to_response(r) for r in rules],
    )


@router.get("/alerts", response_model=AlertListResponse)
def get_alerts(
    dataset: str = Query(...),
    well_id: str = Query(...),
    current_depth_m: Optional[float] = Query(None, ge=0),
    current_formation: Optional[str] = Query(None, max_length=100),
    radius_km: float = Query(50.0, gt=0, le=500),
    limit: int = Query(50, ge=1, le=200),
    conn=Depends(get_conn),
):
    """Alerts derived from risk assessments (above LOW) + triggered rules.

    Alerts are decision-support only — the response body's
    ``recommended_action`` is drawn from a static, human-authored
    dictionary in ``risk/alerts.py``, never generated by an LLM.
    """
    try:
        correlated = correlate_historical_events(
            well_id=well_id, dataset=dataset,
            current_depth_m=current_depth_m,
            current_formation=current_formation,
            radius_km=radius_km, limit=limit, conn=conn,
        )
    except Exception as exc:
        logger.exception("event correlation failed: %s", exc)
        raise HTTPException(status_code=500, detail="event correlation failed")

    well_evidence = _gather_well_evidence_safe(well_id, dataset, current_depth_m, conn)

    assessments = assess_all_risks(
        correlated_events=correlated,
        current_depth_m=current_depth_m,
        current_formation=current_formation,
        well_evidence=well_evidence,
    )
    rules = evaluate_all_rules(correlated, current_formation=current_formation)
    alerts = generate_all_alerts(assessments, rules, well_id=well_id, dataset=dataset)

    return AlertListResponse(
        well_id=well_id, dataset=dataset,
        count=len(alerts), alerts=[_alert_to_response(a) for a in alerts],
    )
