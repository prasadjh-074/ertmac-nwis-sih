"""Comprehensive tests for the risk intelligence and alert engine.

Covers: models, scoring (with and without supplementary evidence),
rules, alerts, provenance, missing-data fallbacks, and LangGraph
node integration.
"""

from __future__ import annotations

import pytest

from events.models import (
    CorrelatedEvent,
    DrillingEvent,
    EventProvenance,
    EventSeverity,
    EventType,
)
from risk.models import (
    Alert,
    AlertSeverity,
    RiskAssessment,
    RiskLevel,
    RiskMethodology,
    RiskType,
    RuleResult,
    RuleType,
)
from risk.scoring import (
    _compute_supplementary_score,
    _score_to_level,
    assess_all_risks,
    assess_single_risk,
)
from risk.rules import (
    evaluate_all_rules,
    rule_cementing_history_warning,
    rule_formation_history_warning,
    rule_high_risk_event_cluster,
    rule_kick_history_warning,
    rule_nearby_mud_loss,
    rule_nearby_stuck_pipe,
    rule_torque_history_warning,
)
from risk.alerts import (
    generate_alerts_from_risks,
    generate_alerts_from_rules,
    generate_all_alerts,
)
from risk.evidence_sources import (
    CaliperEvidence,
    MudWeightEvidence,
    PressureEvidence,
    WellEvidenceSummary,
)


# ── Fixtures ───────────────────────────────────────────────────

def _make_event(
    event_type: EventType = EventType.MUD_LOSS,
    severity: EventSeverity = EventSeverity.MEDIUM,
    depth_start_m: float = 2000.0,
    formation: str = "Draupne",
) -> DrillingEvent:
    return DrillingEvent(
        event_type=event_type,
        severity=severity,
        description="test event",
        depth_start_m=depth_start_m,
        formation=formation,
        provenance=EventProvenance(
            source_type="sodir_history",
            extraction_method="regex",
        ),
    )


def _make_correlated(
    event_type: EventType = EventType.MUD_LOSS,
    severity: EventSeverity = EventSeverity.MEDIUM,
    depth_start_m: float = 2000.0,
    formation: str = "Draupne",
    source_well_id: str = "15/3-1",
    source_dataset: str = "SODIR",
    distance_km: float = 10.0,
    depth_overlap: bool = False,
    formation_match: bool = False,
    own_well: bool = False,
) -> CorrelatedEvent:
    event = _make_event(event_type, severity, depth_start_m, formation)
    factors = {}
    if own_well:
        factors["own_well"] = True
    return CorrelatedEvent(
        event=event,
        source_well_id=source_well_id,
        source_dataset=source_dataset,
        distance_km=None if own_well else distance_km,
        depth_overlap=depth_overlap,
        formation_match=formation_match,
        relevance_factors=factors,
    )


def _make_well_evidence(
    pressures=None, mud_weights=None, caliper=None,
) -> WellEvidenceSummary:
    return WellEvidenceSummary(
        pressure_evidence=pressures or [],
        mud_weight_evidence=mud_weights or [],
        caliper_evidence=caliper or [],
    )


# ── Model tests ────────────────────────────────────────────────

class TestRiskModels:

    def test_risk_type_enum_values(self):
        assert len(RiskType) == 5
        assert RiskType.MUD_LOSS_RISK.value == "mud_loss_risk"
        assert RiskType.KICK_OVERPRESSURE_RISK.value == "kick_overpressure_risk"

    def test_risk_level_enum_values(self):
        assert RiskLevel.LOW.value == "low"
        assert RiskLevel.HIGH.value == "high"

    def test_risk_assessment_default_limitations(self):
        ra = RiskAssessment(
            risk_type=RiskType.MUD_LOSS_RISK,
            score=0.5,
            level=RiskLevel.MEDIUM,
            confidence=0.3,
        )
        assert len(ra.limitations) == 3
        assert "heuristic" in ra.limitations[0].lower()
        assert ra.methodology == RiskMethodology.EVIDENCE_RULE_BASED

    def test_risk_assessment_custom_limitations(self):
        ra = RiskAssessment(
            risk_type=RiskType.MUD_LOSS_RISK,
            score=0.5,
            level=RiskLevel.MEDIUM,
            confidence=0.3,
            limitations=["custom limitation"],
        )
        assert ra.limitations == ["custom limitation"]

    def test_rule_type_enum_count(self):
        assert len(RuleType) == 7

    def test_alert_severity_ordering(self):
        severities = list(AlertSeverity)
        assert AlertSeverity.INFO in severities
        assert AlertSeverity.CRITICAL in severities

    def test_alert_default_fields(self):
        a = Alert()
        assert a.alert_id is None
        assert a.severity == AlertSeverity.INFO
        assert a.evidence == []

    def test_rule_result_defaults(self):
        rr = RuleResult(rule_type=RuleType.KICK_HISTORY_WARNING, triggered=False)
        assert rr.severity == RiskLevel.UNKNOWN
        assert rr.evidence == []


# ── Scoring engine tests ──────────────────────────────────────

class TestScoring:

    def test_score_to_level_low(self):
        assert _score_to_level(0.0) == RiskLevel.LOW
        assert _score_to_level(0.29) == RiskLevel.LOW

    def test_score_to_level_medium(self):
        assert _score_to_level(0.3) == RiskLevel.MEDIUM
        assert _score_to_level(0.59) == RiskLevel.MEDIUM

    def test_score_to_level_high(self):
        assert _score_to_level(0.6) == RiskLevel.HIGH
        assert _score_to_level(1.0) == RiskLevel.HIGH

    def test_no_events_returns_low_score(self):
        ra = assess_single_risk(RiskType.MUD_LOSS_RISK, [])
        assert ra.score == 0.0
        assert ra.level == RiskLevel.LOW
        assert ra.confidence == 0.0

    def test_single_event_scores_nonzero(self):
        events = [_make_correlated(EventType.MUD_LOSS)]
        ra = assess_single_risk(RiskType.MUD_LOSS_RISK, events)
        assert ra.score > 0.0
        assert ra.risk_type == RiskType.MUD_LOSS_RISK
        assert ra.model_or_rule_source == "evidence_rule_based"

    def test_more_events_higher_score(self):
        one = [_make_correlated(EventType.MUD_LOSS)]
        three = [
            _make_correlated(EventType.MUD_LOSS, source_well_id=f"well-{i}")
            for i in range(3)
        ]
        ra_one = assess_single_risk(RiskType.MUD_LOSS_RISK, one)
        ra_three = assess_single_risk(RiskType.MUD_LOSS_RISK, three)
        assert ra_three.score > ra_one.score

    def test_closer_events_higher_score(self):
        far = [_make_correlated(EventType.MUD_LOSS, distance_km=40.0)]
        near = [_make_correlated(EventType.MUD_LOSS, distance_km=2.0)]
        ra_far = assess_single_risk(RiskType.MUD_LOSS_RISK, far)
        ra_near = assess_single_risk(RiskType.MUD_LOSS_RISK, near)
        assert ra_near.score > ra_far.score

    def test_depth_overlap_increases_score(self):
        no_overlap = [_make_correlated(EventType.MUD_LOSS, depth_overlap=False)]
        with_overlap = [_make_correlated(EventType.MUD_LOSS, depth_overlap=True)]
        ra_no = assess_single_risk(RiskType.MUD_LOSS_RISK, no_overlap)
        ra_yes = assess_single_risk(RiskType.MUD_LOSS_RISK, with_overlap)
        assert ra_yes.score > ra_no.score

    def test_formation_match_increases_score(self):
        no_match = [_make_correlated(EventType.MUD_LOSS, formation_match=False)]
        with_match = [_make_correlated(EventType.MUD_LOSS, formation_match=True)]
        ra_no = assess_single_risk(RiskType.MUD_LOSS_RISK, no_match)
        ra_yes = assess_single_risk(RiskType.MUD_LOSS_RISK, with_match)
        assert ra_yes.score > ra_no.score

    def test_own_well_gets_proximity_1(self):
        own = [_make_correlated(EventType.MUD_LOSS, own_well=True)]
        ra = assess_single_risk(RiskType.MUD_LOSS_RISK, own)
        assert ra.contributing_features["proximity_factor"] == 1.0

    def test_irrelevant_event_types_ignored(self):
        events = [_make_correlated(EventType.STUCK_PIPE)]
        ra = assess_single_risk(RiskType.MUD_LOSS_RISK, events)
        assert ra.score == 0.0
        assert ra.contributing_features["event_count"] == 0

    def test_score_capped_at_1(self):
        events = [
            _make_correlated(
                EventType.MUD_LOSS,
                source_well_id=f"w-{i}",
                distance_km=1.0,
                depth_overlap=True,
                formation_match=True,
                severity=EventSeverity.CRITICAL,
            )
            for i in range(20)
        ]
        ra = assess_single_risk(RiskType.MUD_LOSS_RISK, events)
        assert ra.score <= 1.0

    def test_confidence_increases_with_evidence(self):
        one = [_make_correlated(EventType.MUD_LOSS)]
        five = [
            _make_correlated(EventType.MUD_LOSS, source_well_id=f"w-{i}")
            for i in range(5)
        ]
        ra_one = assess_single_risk(RiskType.MUD_LOSS_RISK, one)
        ra_five = assess_single_risk(RiskType.MUD_LOSS_RISK, five)
        assert ra_five.confidence > ra_one.confidence

    def test_historical_events_capped_at_5(self):
        events = [
            _make_correlated(EventType.MUD_LOSS, source_well_id=f"w-{i}")
            for i in range(10)
        ]
        ra = assess_single_risk(RiskType.MUD_LOSS_RISK, events)
        assert len(ra.historical_events) <= 5

    def test_evidence_lines_populated(self):
        events = [
            _make_correlated(EventType.MUD_LOSS, depth_overlap=True, formation_match=True)
        ]
        ra = assess_single_risk(RiskType.MUD_LOSS_RISK, events)
        evidence_text = " ".join(ra.evidence)
        assert "historical" in evidence_text.lower()
        assert "overlap" in evidence_text.lower()
        assert "formation" in evidence_text.lower()

    def test_contributing_features_populated(self):
        events = [_make_correlated(EventType.MUD_LOSS)]
        ra = assess_single_risk(RiskType.MUD_LOSS_RISK, events)
        f = ra.contributing_features
        assert "event_count" in f
        assert "frequency_score" in f
        assert "proximity_factor" in f
        assert "depth_factor" in f
        assert "formation_factor" in f
        assert "avg_severity" in f

    def test_assess_all_risks_returns_5(self):
        events = [_make_correlated(EventType.MUD_LOSS)]
        results = assess_all_risks(events)
        assert len(results) == 5
        types = {r.risk_type for r in results}
        assert types == set(RiskType)

    def test_kick_overpressure_maps_kick_and_overpressure(self):
        kick = [_make_correlated(EventType.KICK)]
        overpressure = [_make_correlated(EventType.OVERPRESSURE)]
        ra_kick = assess_single_risk(RiskType.KICK_OVERPRESSURE_RISK, kick)
        ra_op = assess_single_risk(RiskType.KICK_OVERPRESSURE_RISK, overpressure)
        assert ra_kick.score > 0
        assert ra_op.score > 0


# ── Supplementary evidence (DST/mud/caliper) scoring tests ───

class TestSupplementaryScoring:

    def test_kick_risk_with_pressure_evidence(self):
        evidence = _make_well_evidence(
            pressures=[
                PressureEvidence(
                    wellbore_id=1, well_id="w1", dataset="SODIR",
                    from_depth_m=2000, to_depth_m=2100,
                    shut_in_pressure=300, flow_pressure=250,
                    bottom_hole_pressure=350,
                ),
            ],
        )
        events = [_make_correlated(EventType.KICK)]
        ra_with = assess_single_risk(RiskType.KICK_OVERPRESSURE_RISK, events, well_evidence=evidence)
        ra_without = assess_single_risk(RiskType.KICK_OVERPRESSURE_RISK, events)
        assert ra_with.confidence > ra_without.confidence
        assert any("DST" in e or "BHP" in e for e in ra_with.evidence)

    def test_kick_risk_with_high_mud_weight(self):
        evidence = _make_well_evidence(
            mud_weights=[
                MudWeightEvidence(
                    wellbore_id=1, well_id="w1", dataset="SODIR",
                    depth_m=2000, mud_weight=1.6,
                ),
            ],
        )
        events = [_make_correlated(EventType.KICK)]
        ra = assess_single_risk(RiskType.KICK_OVERPRESSURE_RISK, events, well_evidence=evidence)
        assert any("mud weight" in e.lower() for e in ra.evidence)

    def test_mud_loss_with_mud_weight(self):
        evidence = _make_well_evidence(
            mud_weights=[
                MudWeightEvidence(
                    wellbore_id=1, well_id="w1", dataset="SODIR",
                    depth_m=2000, mud_weight=1.5,
                ),
            ],
        )
        events = [_make_correlated(EventType.MUD_LOSS)]
        ra = assess_single_risk(RiskType.MUD_LOSS_RISK, events, well_evidence=evidence)
        assert ra.contributing_features.get("supplementary_score", 0) > 0

    def test_stuck_pipe_with_caliper_washout(self):
        evidence = _make_well_evidence(
            caliper=[
                CaliperEvidence(
                    well_id="w1", dataset="FORCE_2020",
                    depth_start_m=1900, depth_end_m=2100,
                    caliper_mean=10.0, caliper_max=12.0,
                    bit_size_mean=8.5, washout_ratio=1.18,
                ),
            ],
        )
        events = [_make_correlated(EventType.STUCK_PIPE)]
        ra = assess_single_risk(RiskType.STUCK_PIPE_RISK, events, well_evidence=evidence)
        assert any("washout" in e.lower() for e in ra.evidence)

    def test_cementing_with_severe_washout(self):
        evidence = _make_well_evidence(
            caliper=[
                CaliperEvidence(
                    well_id="w1", dataset="FORCE_2020",
                    depth_start_m=1900, depth_end_m=2100,
                    caliper_mean=12.0, caliper_max=14.0,
                    bit_size_mean=8.5, washout_ratio=1.25,
                ),
            ],
        )
        events = [_make_correlated(EventType.CEMENTING_ISSUE)]
        ra = assess_single_risk(RiskType.CEMENTING_RISK, events, well_evidence=evidence)
        assert ra.contributing_features.get("supplementary_score", 0) > 0

    def test_supplementary_only_no_events(self):
        evidence = _make_well_evidence(
            pressures=[
                PressureEvidence(
                    wellbore_id=1, well_id="w1", dataset="SODIR",
                    from_depth_m=2000, to_depth_m=2100,
                    shut_in_pressure=300, flow_pressure=250,
                    bottom_hole_pressure=350,
                ),
            ],
        )
        ra = assess_single_risk(RiskType.KICK_OVERPRESSURE_RISK, [], well_evidence=evidence)
        # Even with no events, DST evidence should produce a nonzero score
        assert ra.score > 0

    def test_no_supplementary_for_torque(self):
        evidence = _make_well_evidence(
            pressures=[
                PressureEvidence(
                    wellbore_id=1, well_id="w1", dataset="SODIR",
                    from_depth_m=2000, to_depth_m=2100,
                    shut_in_pressure=300, flow_pressure=250,
                    bottom_hole_pressure=350,
                ),
            ],
        )
        result = _compute_supplementary_score(RiskType.TORQUE_SPIKE_RISK, evidence)
        assert result["score"] == 0.0

    def test_empty_evidence_summary(self):
        evidence = _make_well_evidence()
        events = [_make_correlated(EventType.MUD_LOSS)]
        ra = assess_single_risk(RiskType.MUD_LOSS_RISK, events, well_evidence=evidence)
        assert ra.score > 0


# ── Rule engine tests ─────────────────────────────────────────

class TestRules:

    def test_formation_history_warning_triggers(self):
        events = [
            _make_correlated(EventType.MUD_LOSS, formation="Draupne", formation_match=True),
            _make_correlated(EventType.STUCK_PIPE, formation="Draupne", formation_match=True),
        ]
        result = rule_formation_history_warning(events, "Draupne")
        assert result.triggered
        assert result.rule_type == RuleType.FORMATION_HISTORY_WARNING

    def test_formation_history_warning_no_trigger_without_formation(self):
        events = [_make_correlated(EventType.MUD_LOSS)]
        result = rule_formation_history_warning(events, None)
        assert not result.triggered

    def test_nearby_stuck_pipe_triggers(self):
        events = [
            _make_correlated(
                EventType.STUCK_PIPE,
                source_well_id="other-well",
                distance_km=5.0,
            ),
        ]
        result = rule_nearby_stuck_pipe(events)
        assert result.triggered
        assert result.rule_type == RuleType.NEARBY_STUCK_PIPE_HISTORY

    def test_nearby_stuck_pipe_excludes_own_well(self):
        events = [
            _make_correlated(EventType.STUCK_PIPE, own_well=True),
        ]
        result = rule_nearby_stuck_pipe(events)
        assert not result.triggered

    def test_nearby_mud_loss_triggers(self):
        events = [
            _make_correlated(EventType.MUD_LOSS, source_well_id="other", distance_km=8.0),
        ]
        result = rule_nearby_mud_loss(events)
        assert result.triggered

    def test_kick_history_warning_triggers(self):
        events = [_make_correlated(EventType.KICK)]
        result = rule_kick_history_warning(events)
        assert result.triggered
        assert result.severity == RiskLevel.HIGH

    def test_kick_history_no_kicks(self):
        events = [_make_correlated(EventType.MUD_LOSS)]
        result = rule_kick_history_warning(events)
        assert not result.triggered

    def test_torque_history_triggers(self):
        events = [_make_correlated(EventType.TORQUE_SPIKE)]
        result = rule_torque_history_warning(events)
        assert result.triggered

    def test_cementing_history_triggers(self):
        events = [_make_correlated(EventType.CEMENTING_ISSUE)]
        result = rule_cementing_history_warning(events)
        assert result.triggered

    def test_high_risk_event_cluster_triggers(self):
        events = [
            _make_correlated(EventType.MUD_LOSS, severity=EventSeverity.HIGH),
            _make_correlated(EventType.STUCK_PIPE, severity=EventSeverity.HIGH),
            _make_correlated(EventType.KICK, severity=EventSeverity.CRITICAL),
        ]
        result = rule_high_risk_event_cluster(events)
        assert result.triggered
        assert result.severity == RiskLevel.HIGH

    def test_high_risk_event_cluster_not_enough_types(self):
        events = [
            _make_correlated(EventType.MUD_LOSS, severity=EventSeverity.HIGH),
            _make_correlated(EventType.MUD_LOSS, severity=EventSeverity.HIGH),
            _make_correlated(EventType.MUD_LOSS, severity=EventSeverity.HIGH),
        ]
        result = rule_high_risk_event_cluster(events)
        assert not result.triggered

    def test_evaluate_all_rules_returns_7(self):
        events = [_make_correlated(EventType.MUD_LOSS)]
        results = evaluate_all_rules(events)
        assert len(results) == 7
        types = {r.rule_type for r in results}
        assert types == set(RuleType)

    def test_empty_events_no_rules_trigger(self):
        results = evaluate_all_rules([])
        assert all(not r.triggered for r in results)

    def test_rule_evidence_is_list_of_strings(self):
        events = [_make_correlated(EventType.KICK)]
        results = evaluate_all_rules(events)
        for r in results:
            assert isinstance(r.evidence, list)
            for e in r.evidence:
                assert isinstance(e, str)


# ── Alert generation tests ────────────────────────────────────

class TestAlerts:

    def test_low_risk_produces_no_alert(self):
        assessments = [
            RiskAssessment(
                risk_type=RiskType.MUD_LOSS_RISK,
                score=0.1,
                level=RiskLevel.LOW,
                confidence=0.2,
            ),
        ]
        alerts = generate_alerts_from_risks(assessments)
        assert len(alerts) == 0

    def test_medium_risk_produces_warning_alert(self):
        assessments = [
            RiskAssessment(
                risk_type=RiskType.MUD_LOSS_RISK,
                score=0.45,
                level=RiskLevel.MEDIUM,
                confidence=0.4,
                evidence=["2 events found."],
            ),
        ]
        alerts = generate_alerts_from_risks(assessments)
        assert len(alerts) == 1
        assert alerts[0].severity == AlertSeverity.WARNING
        assert alerts[0].alert_type == "mud_loss_risk"

    def test_high_risk_produces_high_alert(self):
        assessments = [
            RiskAssessment(
                risk_type=RiskType.KICK_OVERPRESSURE_RISK,
                score=0.7,
                level=RiskLevel.HIGH,
                confidence=0.6,
                evidence=["kick event found"],
            ),
        ]
        alerts = generate_alerts_from_risks(assessments)
        assert len(alerts) == 1
        assert alerts[0].severity == AlertSeverity.HIGH
        assert "well control" in alerts[0].recommended_action.lower()

    def test_alert_has_provenance(self):
        assessments = [
            RiskAssessment(
                risk_type=RiskType.MUD_LOSS_RISK,
                score=0.5,
                level=RiskLevel.MEDIUM,
                confidence=0.4,
            ),
        ]
        alerts = generate_alerts_from_risks(assessments, "15/3-1", "SODIR")
        assert len(alerts) == 1
        assert "evidence_rule_based" in alerts[0].provenance
        assert alerts[0].context["well_id"] == "15/3-1"
        assert alerts[0].context["methodology"] == "evidence_rule_based"

    def test_rule_alert_generated_for_triggered_rule(self):
        rules = [
            RuleResult(
                rule_type=RuleType.KICK_HISTORY_WARNING,
                triggered=True,
                severity=RiskLevel.HIGH,
                evidence=["Kick event in nearby well."],
            ),
        ]
        alerts = generate_alerts_from_rules(rules, "w1", "SODIR")
        assert len(alerts) == 1
        assert alerts[0].severity == AlertSeverity.HIGH
        assert "deterministic_rule" in alerts[0].provenance

    def test_rule_alert_not_generated_for_untriggered(self):
        rules = [
            RuleResult(
                rule_type=RuleType.KICK_HISTORY_WARNING,
                triggered=False,
            ),
        ]
        alerts = generate_alerts_from_rules(rules)
        assert len(alerts) == 0

    def test_generate_all_alerts_sorted_by_severity(self):
        assessments = [
            RiskAssessment(
                risk_type=RiskType.MUD_LOSS_RISK,
                score=0.45,
                level=RiskLevel.MEDIUM,
                confidence=0.4,
                evidence=["mud loss"],
            ),
            RiskAssessment(
                risk_type=RiskType.KICK_OVERPRESSURE_RISK,
                score=0.7,
                level=RiskLevel.HIGH,
                confidence=0.6,
                evidence=["kick"],
            ),
        ]
        rules = [
            RuleResult(
                rule_type=RuleType.FORMATION_HISTORY_WARNING,
                triggered=True,
                severity=RiskLevel.MEDIUM,
                evidence=["formation warning"],
            ),
        ]
        alerts = generate_all_alerts(assessments, rules, "w1", "SODIR")
        assert len(alerts) == 3
        # HIGH should come before WARNING
        assert alerts[0].severity == AlertSeverity.HIGH

    def test_alert_explanation_includes_evidence(self):
        assessments = [
            RiskAssessment(
                risk_type=RiskType.STUCK_PIPE_RISK,
                score=0.5,
                level=RiskLevel.MEDIUM,
                confidence=0.4,
                evidence=["2 stuck pipe events near current depth."],
                contributing_features={"event_count": 2, "distinct_wells": 1},
            ),
        ]
        alerts = generate_alerts_from_risks(assessments)
        assert "stuck pipe" in alerts[0].explanation.lower()

    def test_each_risk_type_has_recommendations(self):
        for rt in RiskType:
            assessments = [
                RiskAssessment(
                    risk_type=rt,
                    score=0.5,
                    level=RiskLevel.MEDIUM,
                    confidence=0.3,
                ),
            ]
            alerts = generate_alerts_from_risks(assessments)
            assert len(alerts) == 1
            assert alerts[0].recommended_action


# ── Provenance and transparency tests ─────────────────────────

class TestProvenance:

    def test_risk_assessment_always_evidence_based(self):
        events = [_make_correlated(EventType.MUD_LOSS)]
        results = assess_all_risks(events)
        for ra in results:
            assert ra.methodology == RiskMethodology.EVIDENCE_RULE_BASED
            assert ra.model_or_rule_source == "evidence_rule_based"

    def test_limitations_always_populated(self):
        events = [_make_correlated(EventType.MUD_LOSS)]
        results = assess_all_risks(events)
        for ra in results:
            assert len(ra.limitations) >= 1

    def test_alert_provenance_traces_to_source(self):
        assessments = [
            RiskAssessment(
                risk_type=RiskType.MUD_LOSS_RISK,
                score=0.5,
                level=RiskLevel.MEDIUM,
                confidence=0.4,
            ),
        ]
        rules = [
            RuleResult(
                rule_type=RuleType.KICK_HISTORY_WARNING,
                triggered=True,
                severity=RiskLevel.HIGH,
                evidence=["kick in area"],
            ),
        ]
        alerts = generate_all_alerts(assessments, rules)
        provenances = [p for a in alerts for p in a.provenance]
        assert "evidence_rule_based" in provenances
        assert "deterministic_rule" in provenances


# ── Missing data / fallback tests ─────────────────────────────

class TestMissingData:

    def test_empty_events_all_risks_low(self):
        results = assess_all_risks([])
        for ra in results:
            assert ra.level == RiskLevel.LOW
            assert ra.score == 0.0

    def test_empty_events_no_alerts(self):
        results = assess_all_risks([])
        rules = evaluate_all_rules([])
        alerts = generate_all_alerts(results, rules)
        assert len(alerts) == 0

    def test_none_well_evidence(self):
        events = [_make_correlated(EventType.MUD_LOSS)]
        ra = assess_single_risk(RiskType.MUD_LOSS_RISK, events, well_evidence=None)
        assert ra.score > 0.0

    def test_empty_well_evidence(self):
        evidence = _make_well_evidence()
        events = [_make_correlated(EventType.MUD_LOSS)]
        ra = assess_single_risk(RiskType.MUD_LOSS_RISK, events, well_evidence=evidence)
        assert ra.score > 0.0
        assert ra.contributing_features["supplementary_score"] == 0.0

    def test_only_supplementary_no_events_but_no_supplement(self):
        evidence = _make_well_evidence()
        ra = assess_single_risk(RiskType.KICK_OVERPRESSURE_RISK, [], well_evidence=evidence)
        assert ra.score == 0.0
        assert ra.level == RiskLevel.LOW


# ── LangGraph node integration tests ─────────────────────────

class TestLangGraphNodes:

    def test_assess_risk_node_skips_without_query(self):
        from graph.nodes import assess_risk_node
        from graph.state import ExecutionMetadata, GraphState

        state: GraphState = {
            "user_question": "hello",
            "structured_query": None,
            "execution_metadata": ExecutionMetadata(),
            "errors": [],
        }
        result = assess_risk_node(state)
        assert result["execution_metadata"].node_status["assess_risk"] == "skipped"

    def test_generate_alerts_node_skips_without_assessments(self):
        from graph.nodes import generate_alerts_node
        from graph.state import ExecutionMetadata, GraphState

        state: GraphState = {
            "user_question": "hello",
            "structured_query": None,
            "risk_assessments": None,
            "rule_results": None,
            "execution_metadata": ExecutionMetadata(),
        }
        result = generate_alerts_node(state)
        assert result["execution_metadata"].node_status["generate_alerts"] == "skipped"

    def test_generate_alerts_node_produces_alerts(self):
        from graph.nodes import generate_alerts_node
        from graph.state import ExecutionMetadata, GraphState

        state: GraphState = {
            "user_question": "",
            "structured_query": None,
            "risk_assessments": [
                RiskAssessment(
                    risk_type=RiskType.MUD_LOSS_RISK,
                    score=0.5,
                    level=RiskLevel.MEDIUM,
                    confidence=0.4,
                    evidence=["test"],
                ),
            ],
            "rule_results": [],
            "execution_metadata": ExecutionMetadata(),
        }
        result = generate_alerts_node(state)
        assert result["execution_metadata"].node_status["generate_alerts"] == "success"
        assert len(result["alerts"]) == 1

    def test_query_response_includes_risk_fields(self):
        from graph.state import QueryResponse
        resp = QueryResponse(answer="test")
        assert resp.risk_assessments == []
        assert resp.alerts == []


# ── Graph state tests ─────────────────────────────────────────

class TestGraphState:

    def test_graph_state_has_risk_fields(self):
        from graph.state import GraphState
        state: GraphState = {
            "user_question": "",
            "risk_assessments": None,
            "rule_results": None,
            "alerts": None,
        }
        assert state["risk_assessments"] is None

    def test_query_response_with_risk_data(self):
        from graph.state import QueryResponse
        ra = RiskAssessment(
            risk_type=RiskType.MUD_LOSS_RISK,
            score=0.5,
            level=RiskLevel.MEDIUM,
            confidence=0.3,
        )
        alert = Alert(
            alert_id=1,
            alert_type="mud_loss_risk",
            severity=AlertSeverity.WARNING,
            title="test",
        )
        resp = QueryResponse(
            answer="test",
            risk_assessments=[ra],
            alerts=[alert],
        )
        assert len(resp.risk_assessments) == 1
        assert len(resp.alerts) == 1
