"""Metric computation over evaluation results."""

from __future__ import annotations

from typing import List

from .models import MetricResult, QueryEvalResult


def intent_accuracy(results: List[QueryEvalResult]) -> MetricResult:
    relevant = [r for r in results if "intent" in r.checks]
    passed = sum(1 for r in relevant if r.checks.get("intent"))
    return MetricResult(
        name="intent_accuracy",
        value=passed / len(relevant) if relevant else 1.0,
        total=len(relevant),
        passed=passed,
    )


def entity_accuracy(results: List[QueryEvalResult]) -> MetricResult:
    relevant = [r for r in results if "status" in r.checks]
    passed = sum(1 for r in relevant if r.checks.get("status"))
    return MetricResult(
        name="entity_accuracy",
        value=passed / len(relevant) if relevant else 1.0,
        total=len(relevant),
        passed=passed,
    )


def result_presence(results: List[QueryEvalResult]) -> MetricResult:
    relevant = [r for r in results if "min_result_count" in r.checks]
    passed = sum(1 for r in relevant if r.checks.get("min_result_count"))
    return MetricResult(
        name="result_presence",
        value=passed / len(relevant) if relevant else 1.0,
        total=len(relevant),
        passed=passed,
    )


def source_correctness(results: List[QueryEvalResult]) -> MetricResult:
    relevant = [r for r in results if "sources_contain" in r.checks]
    passed = sum(1 for r in relevant if r.checks.get("sources_contain"))
    return MetricResult(
        name="source_correctness",
        value=passed / len(relevant) if relevant else 1.0,
        total=len(relevant),
        passed=passed,
    )


def provenance_completeness(results: List[QueryEvalResult]) -> MetricResult:
    relevant = [r for r in results if "sources_contain" in r.checks or "confidence_label" in r.checks]
    passed = sum(1 for r in relevant if r.checks.get("sources_contain", True) and r.checks.get("confidence_label", True))
    return MetricResult(
        name="provenance_completeness",
        value=passed / len(relevant) if relevant else 1.0,
        total=len(relevant),
        passed=passed,
    )


def resolver_success_rate(results: List[QueryEvalResult]) -> MetricResult:
    relevant = [r for r in results if not r.known_limitation and r.error is None
                and "status" in r.checks]
    passed = sum(1 for r in relevant if r.checks.get("status"))
    return MetricResult(
        name="resolver_success_rate",
        value=passed / len(relevant) if relevant else 1.0,
        total=len(relevant),
        passed=passed,
    )


def invalid_query_handling(results: List[QueryEvalResult]) -> MetricResult:
    relevant = [r for r in results if "validation_rejected" in r.checks]
    passed = sum(1 for r in relevant if r.checks.get("validation_rejected"))
    return MetricResult(
        name="invalid_query_handling",
        value=passed / len(relevant) if relevant else 1.0,
        total=len(relevant),
        passed=passed,
    )


def confidence_accuracy(results: List[QueryEvalResult]) -> MetricResult:
    relevant = [r for r in results if "confidence_label" in r.checks]
    passed = sum(1 for r in relevant if r.checks.get("confidence_label"))
    return MetricResult(
        name="confidence_accuracy",
        value=passed / len(relevant) if relevant else 1.0,
        total=len(relevant),
        passed=passed,
    )


def evidence_presence(results: List[QueryEvalResult]) -> MetricResult:
    relevant = [r for r in results if "evidence_present" in r.checks]
    passed = sum(1 for r in relevant if r.checks.get("evidence_present"))
    return MetricResult(
        name="evidence_presence",
        value=passed / len(relevant) if relevant else 1.0,
        total=len(relevant),
        passed=passed,
    )


def rationale_presence(results: List[QueryEvalResult]) -> MetricResult:
    relevant = [r for r in results if "rationale_present" in r.checks]
    passed = sum(1 for r in relevant if r.checks.get("rationale_present"))
    return MetricResult(
        name="rationale_presence",
        value=passed / len(relevant) if relevant else 1.0,
        total=len(relevant),
        passed=passed,
    )


def unsupported_claim_count(results: List[QueryEvalResult]) -> MetricResult:
    relevant = [r for r in results if "no_unsupported_claims" in r.checks]
    passed = sum(1 for r in relevant if r.checks.get("no_unsupported_claims"))
    return MetricResult(
        name="unsupported_claim_count",
        value=passed / len(relevant) if relevant else 1.0,
        total=len(relevant),
        passed=passed,
    )


def document_result_presence(results: List[QueryEvalResult]) -> MetricResult:
    relevant = [r for r in results if "min_document_result_count" in r.checks]
    passed = sum(1 for r in relevant if r.checks.get("min_document_result_count"))
    return MetricResult(
        name="document_result_presence",
        value=passed / len(relevant) if relevant else 1.0,
        total=len(relevant),
        passed=passed,
    )


def document_provenance_completeness(results: List[QueryEvalResult]) -> MetricResult:
    relevant = [r for r in results if "document_provenance_present" in r.checks]
    passed = sum(1 for r in relevant if r.checks.get("document_provenance_present"))
    return MetricResult(
        name="document_provenance_completeness",
        value=passed / len(relevant) if relevant else 1.0,
        total=len(relevant),
        passed=passed,
    )


def document_hit_at_k(results: List[QueryEvalResult]) -> MetricResult:
    relevant = [r for r in results if "document_hit_at_k" in r.checks]
    passed = sum(1 for r in relevant if r.checks.get("document_hit_at_k"))
    return MetricResult(
        name="document_hit_at_k",
        value=passed / len(relevant) if relevant else 1.0,
        total=len(relevant),
        passed=passed,
    )


def overall_pass_rate(results: List[QueryEvalResult]) -> MetricResult:
    passed = sum(1 for r in results if r.passed)
    return MetricResult(
        name="overall_pass_rate",
        value=passed / len(results) if results else 1.0,
        total=len(results),
        passed=passed,
    )


ALL_METRICS = [
    intent_accuracy,
    entity_accuracy,
    result_presence,
    source_correctness,
    provenance_completeness,
    resolver_success_rate,
    invalid_query_handling,
    confidence_accuracy,
    evidence_presence,
    rationale_presence,
    unsupported_claim_count,
    document_result_presence,
    document_provenance_completeness,
    document_hit_at_k,
    overall_pass_rate,
]


def compute_all_metrics(results: List[QueryEvalResult]) -> List[MetricResult]:
    return [fn(results) for fn in ALL_METRICS]
