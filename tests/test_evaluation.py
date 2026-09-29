"""Tests for the evaluation framework."""

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from evaluation.loader import filter_queries, load_golden_dataset
from evaluation.metrics import (
    compute_all_metrics,
    confidence_accuracy,
    entity_accuracy,
    intent_accuracy,
    invalid_query_handling,
    overall_pass_rate,
    result_presence,
    resolver_success_rate,
    source_correctness,
)
from evaluation.models import (
    EvaluationReport,
    GoldenDataset,
    GoldenExpected,
    GoldenQuery,
    MetricResult,
    QueryEvalResult,
)
from evaluation.runner import (
    _check_response,
    format_report_markdown,
    run_structured_evaluation,
    save_report,
)
from graph.errors import GraphError
from graph.state import ConfidenceScore, EvidenceItem, ExecutionMetadata, QueryResponse

DATA_DIR = Path(__file__).resolve().parent.parent / "data" / "evaluation"


# ---------------------------------------------------------------------------
# Loader tests
# ---------------------------------------------------------------------------

class TestLoader:
    def test_load_golden_dataset(self):
        ds = load_golden_dataset()
        assert isinstance(ds, GoldenDataset)
        assert len(ds.queries) >= 20
        assert ds.version == "1.0.0"

    def test_all_queries_have_required_fields(self):
        ds = load_golden_dataset()
        for q in ds.queries:
            assert q.id
            assert q.intent
            assert q.description
            assert q.structured_query
            assert q.expected

    def test_ids_are_unique(self):
        ds = load_golden_dataset()
        ids = [q.id for q in ds.queries]
        assert len(ids) == len(set(ids)), f"Duplicate IDs found: {[x for x in ids if ids.count(x) > 1]}"

    def test_all_six_intents_covered(self):
        ds = load_golden_dataset()
        intents = {q.intent for q in ds.queries}
        expected_intents = {"similar_wells", "similar_windows", "well_information",
                           "formation_information", "compare_wells", "geological_context", "invalid"}
        assert expected_intents <= intents

    def test_filter_by_intent(self):
        ds = load_golden_dataset()
        sw = filter_queries(ds, intent="similar_wells")
        assert all(q.intent == "similar_wells" for q in sw)
        assert len(sw) >= 3

    def test_filter_by_tag(self):
        ds = load_golden_dataset()
        edge = filter_queries(ds, tags=["edge-case"])
        assert all("edge-case" in q.tags for q in edge)
        assert len(edge) >= 4

    def test_filter_exclude_tag(self):
        ds = load_golden_dataset()
        no_edge = filter_queries(ds, exclude_tags=["edge-case"])
        assert all("edge-case" not in q.tags for q in no_edge)

    def test_filter_by_id(self):
        ds = load_golden_dataset()
        subset = filter_queries(ds, ids=["sw-01", "wi-01"])
        assert len(subset) == 2
        assert {q.id for q in subset} == {"sw-01", "wi-01"}

    def test_known_limitations_present(self):
        ds = load_golden_dataset()
        assert len(ds.known_limitations) >= 1
        assert any("15/9-19" in kl for kl in ds.known_limitations)

    def test_nl_queries_exist(self):
        ds = load_golden_dataset()
        nl = [q for q in ds.queries if q.natural_language]
        assert len(nl) >= 8

    def test_known_limitation_tagged_queries(self):
        ds = load_golden_dataset()
        kl = filter_queries(ds, tags=["known-limitation"])
        assert len(kl) >= 1
        for q in kl:
            assert q.nl_expected_override is not None


# ---------------------------------------------------------------------------
# Metrics tests
# ---------------------------------------------------------------------------

def _make_result(query_id, passed, checks=None, **kwargs):
    return QueryEvalResult(
        query_id=query_id,
        intent="similar_wells",
        passed=passed,
        checks=checks or {},
        **kwargs,
    )


class TestMetrics:
    def test_intent_accuracy_all_pass(self):
        results = [_make_result("a", True, {"intent": True}),
                   _make_result("b", True, {"intent": True})]
        m = intent_accuracy(results)
        assert m.value == 1.0
        assert m.passed == 2

    def test_intent_accuracy_mixed(self):
        results = [_make_result("a", True, {"intent": True}),
                   _make_result("b", False, {"intent": False})]
        m = intent_accuracy(results)
        assert m.value == 0.5

    def test_entity_accuracy(self):
        results = [_make_result("a", True, {"status": True}),
                   _make_result("b", False, {"status": False}),
                   _make_result("c", True, {"status": True})]
        m = entity_accuracy(results)
        assert m.value == pytest.approx(2 / 3)

    def test_result_presence(self):
        results = [_make_result("a", True, {"min_result_count": True}),
                   _make_result("b", False, {"min_result_count": False})]
        m = result_presence(results)
        assert m.value == 0.5

    def test_invalid_query_handling(self):
        results = [_make_result("a", True, {"validation_rejected": True}),
                   _make_result("b", True, {"validation_rejected": True})]
        m = invalid_query_handling(results)
        assert m.value == 1.0

    def test_confidence_accuracy(self):
        results = [_make_result("a", True, {"confidence_label": True}),
                   _make_result("b", True, {"confidence_label": False})]
        m = confidence_accuracy(results)
        assert m.value == 0.5

    def test_overall_pass_rate(self):
        results = [_make_result("a", True), _make_result("b", False),
                   _make_result("c", True), _make_result("d", True)]
        m = overall_pass_rate(results)
        assert m.value == 0.75

    def test_compute_all_metrics(self):
        results = [_make_result("a", True, {"intent": True, "status": True})]
        metrics = compute_all_metrics(results)
        assert len(metrics) == 15
        names = {m.name for m in metrics}
        assert "intent_accuracy" in names
        assert "overall_pass_rate" in names
        assert "evidence_presence" in names
        assert "rationale_presence" in names
        assert "unsupported_claim_count" in names
        assert "document_result_presence" in names
        assert "document_provenance_completeness" in names
        assert "document_hit_at_k" in names

    def test_empty_results(self):
        metrics = compute_all_metrics([])
        for m in metrics:
            assert m.value == 1.0
            assert m.total == 0


# ---------------------------------------------------------------------------
# Check response tests
# ---------------------------------------------------------------------------

def _make_query_response(
    answer="test",
    intent="similar_wells",
    node_status=None,
    result_count=0,
    provenance=None,
    confidence_label="medium",
    confidence_value=0.5,
    errors=None,
    evidence=None,
    rationale=None,
):
    return QueryResponse(
        answer=answer,
        structured_query={"intent": intent} if intent else None,
        evidence=evidence or [],
        confidence_score=ConfidenceScore(
            value=confidence_value,
            label=confidence_label,
        ),
        rationale=rationale or ["test rationale"],
        provenance=provenance or [],
        metadata=ExecutionMetadata(
            node_status=node_status or {},
            result_count=result_count,
        ),
        errors=errors or [],
    )


class TestCheckResponse:
    def test_success_query_passes(self):
        q = GoldenQuery(
            id="t1", intent="similar_wells", description="test",
            structured_query={"intent": "similar_wells", "target_dataset": "VOLVE", "target_well_id": "15/9-F-1"},
            expected=GoldenExpected(intent="similar_wells", status="success", min_result_count=1),
        )
        resp = _make_query_response(
            intent="similar_wells",
            node_status={"resolve": "success"},
            result_count=5,
            evidence=[EvidenceItem(source_system="VOLVE", entity_type="well", similarity=0.9)],
        )
        result = _check_response(q, resp, False)
        assert result.passed

    def test_wrong_intent_fails(self):
        q = GoldenQuery(
            id="t2", intent="similar_wells", description="test",
            structured_query={"intent": "similar_wells"},
            expected=GoldenExpected(intent="similar_wells"),
        )
        resp = _make_query_response(intent="well_information")
        result = _check_response(q, resp, False)
        assert not result.passed
        assert "intent" in result.failures[0]

    def test_validation_rejection_detected(self):
        q = GoldenQuery(
            id="t3", intent="invalid", description="test",
            structured_query={"intent": "similar_wells"},
            expected=GoldenExpected(should_fail_validation=True, confidence_label_in=["none"]),
        )
        resp = _make_query_response(
            intent=None,
            confidence_label="none",
            confidence_value=0.0,
            errors=[GraphError(stage="validate", error_type="validation", message="bad")],
        )
        result = _check_response(q, resp, True)
        assert result.passed

    def test_sources_contain_check(self):
        q = GoldenQuery(
            id="t4", intent="similar_wells", description="test",
            structured_query={"intent": "similar_wells"},
            expected=GoldenExpected(sources_contain=["SODIR"]),
        )
        resp = _make_query_response(provenance=["FORCE_2020"])
        result = _check_response(q, resp, False)
        assert not result.checks["sources_contain"]

    def test_confidence_label_check(self):
        q = GoldenQuery(
            id="t5", intent="similar_wells", description="test",
            structured_query={"intent": "similar_wells"},
            expected=GoldenExpected(confidence_label_in=["high"]),
        )
        resp = _make_query_response(confidence_label="low")
        result = _check_response(q, resp, False)
        assert not result.checks["confidence_label"]

    def test_known_limitation_tagged(self):
        q = GoldenQuery(
            id="t6", intent="well_information", description="test",
            tags=["known-limitation"],
            structured_query={"intent": "well_information"},
            expected=GoldenExpected(status="success"),
        )
        resp = _make_query_response(
            intent="well_information",
            node_status={"resolve": "success"},
            result_count=0,
        )
        result = _check_response(q, resp, False)
        assert result.known_limitation


# ---------------------------------------------------------------------------
# Report generation tests
# ---------------------------------------------------------------------------

class TestReportGeneration:
    def test_format_report_markdown(self):
        report = EvaluationReport(
            mode="structured",
            total_queries=2,
            passed=1,
            failed=1,
            pass_rate=0.5,
            metrics=[MetricResult(name="overall_pass_rate", value=0.5, total=2, passed=1)],
            results=[
                _make_result("q1", True),
                _make_result("q2", False, failures=["Expected X"]),
            ],
        )
        md = format_report_markdown(report)
        assert "# Evaluation Report (structured)" in md
        assert "50.0%" in md
        assert "Failed Queries" in md
        assert "q2" in md

    def test_save_report(self, tmp_path):
        report = EvaluationReport(
            mode="structured", total_queries=1, passed=1, failed=0, pass_rate=1.0,
        )
        out = tmp_path / "report.json"
        save_report(report, out)
        assert out.exists()
        data = json.loads(out.read_text())
        assert data["mode"] == "structured"


# ---------------------------------------------------------------------------
# Structured evaluation integration test
# ---------------------------------------------------------------------------

@pytest.mark.integration
class TestStructuredEvaluation:
    def test_run_structured_evaluation(self):
        report = run_structured_evaluation()
        assert report.mode == "structured"
        assert report.total_queries >= 20
        assert report.pass_rate > 0.0

        for m in report.metrics:
            assert 0.0 <= m.value <= 1.0

        invalid_results = [r for r in report.results if r.query_id.startswith("inv-")]
        assert len(invalid_results) >= 4
        for r in invalid_results:
            assert r.passed, f"Invalid query {r.query_id} should pass: {r.failures}"

    def test_run_structured_evaluation_with_intent_filter(self):
        report = run_structured_evaluation(intent_filter="similar_wells")
        assert report.total_queries >= 3
        for r in report.results:
            assert r.intent == "similar_wells"

    def test_run_structured_evaluation_with_tag_filter(self):
        report = run_structured_evaluation(tag_filter=["edge-case"])
        assert report.total_queries >= 4
        for r in report.results:
            assert "edge-case" in r.tags
