"""Risk intelligence and alert models.

All risk scores in this system are evidence-based heuristics derived
from historical drilling event frequency, proximity, and correlation.
None are calibrated statistical probabilities or ML model outputs.

Data availability assessment (2026-09-28):
  31 total events across 20 wells out of 128 with embeddings.
  Largest class: mud_loss = 10 events in 9 wells.
  kick=0, torque_spike=0, cementing_issue=0, casing_issue=0.
  INSUFFICIENT for any model-based approach (need ~30-50+ positive
  examples per class with well-level separation).
  ALL risk types are EVIDENCE/RULE-BASED.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class RiskType(str, Enum):
    MUD_LOSS_RISK = "mud_loss_risk"
    STUCK_PIPE_RISK = "stuck_pipe_risk"
    KICK_OVERPRESSURE_RISK = "kick_overpressure_risk"
    TORQUE_SPIKE_RISK = "torque_spike_risk"
    CEMENTING_RISK = "cementing_risk"


class RiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    UNKNOWN = "unknown"


class RiskMethodology(str, Enum):
    EVIDENCE_RULE_BASED = "evidence_rule_based"
    MODEL_BASED = "model_based"


@dataclass
class RiskAssessment:
    """A single risk assessment for one risk type at a given well context.

    score is a heuristic evidence score in [0, 1], NOT a probability.
    level is derived from score thresholds.
    confidence reflects how much supporting evidence was available.
    """

    risk_type: RiskType
    score: float
    level: RiskLevel
    confidence: float
    evidence: List[str] = field(default_factory=list)
    contributing_features: Dict[str, Any] = field(default_factory=dict)
    historical_events: List[Dict[str, Any]] = field(default_factory=list)
    model_or_rule_source: str = "evidence_rule_based"
    methodology: RiskMethodology = RiskMethodology.EVIDENCE_RULE_BASED
    limitations: List[str] = field(default_factory=list)

    def __post_init__(self):
        if self.methodology == RiskMethodology.EVIDENCE_RULE_BASED:
            if not self.limitations:
                self.limitations = [
                    "Score is a heuristic evidence indicator, not a calibrated probability.",
                    "Based on historical event extraction from SODIR narratives (regex/keyword).",
                    "Insufficient labeled data for model-based prediction.",
                ]


class RuleType(str, Enum):
    FORMATION_HISTORY_WARNING = "formation_history_warning"
    NEARBY_STUCK_PIPE_HISTORY = "nearby_stuck_pipe_history"
    NEARBY_MUD_LOSS_HISTORY = "nearby_mud_loss_history"
    KICK_HISTORY_WARNING = "kick_history_warning"
    TORQUE_HISTORY_WARNING = "torque_history_warning"
    CEMENTING_HISTORY_WARNING = "cementing_history_warning"
    HIGH_RISK_EVENT_CLUSTER = "high_risk_event_cluster"


@dataclass
class RuleResult:
    """Output of a single deterministic rule evaluation."""

    rule_type: RuleType
    triggered: bool
    severity: RiskLevel = RiskLevel.UNKNOWN
    evidence: List[str] = field(default_factory=list)
    contributing_events: List[Dict[str, Any]] = field(default_factory=list)
    details: Dict[str, Any] = field(default_factory=dict)


class AlertSeverity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class Alert:
    """An actionable alert generated from risk assessments and rule results.

    Recommendations are decision support only — this system does not
    claim autonomous drilling control.
    """

    alert_id: Optional[int] = None
    alert_type: str = ""
    severity: AlertSeverity = AlertSeverity.INFO
    title: str = ""
    explanation: str = ""
    evidence: List[str] = field(default_factory=list)
    recommended_action: str = ""
    provenance: List[str] = field(default_factory=list)
    context: Dict[str, Any] = field(default_factory=dict)
