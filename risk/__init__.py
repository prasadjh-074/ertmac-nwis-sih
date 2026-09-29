"""Risk intelligence and alert engine.

All risk assessments in this package are EVIDENCE/RULE-BASED.
No model-based predictions — insufficient labeled data (31 events
across 20 wells; largest class mud_loss=10).
"""

from .models import (
    Alert,
    AlertSeverity,
    RiskAssessment,
    RiskLevel,
    RiskMethodology,
    RiskType,
    RuleResult,
    RuleType,
)
from .scoring import assess_all_risks, assess_single_risk
from .rules import evaluate_all_rules
from .alerts import generate_all_alerts

__all__ = [
    "Alert",
    "AlertSeverity",
    "RiskAssessment",
    "RiskLevel",
    "RiskMethodology",
    "RiskType",
    "RuleResult",
    "RuleType",
    "assess_all_risks",
    "assess_single_risk",
    "evaluate_all_rules",
    "generate_all_alerts",
]
