"""Evaluation runners: structured (no LLM) and end-to-end (with Groq)."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from pydantic import ValidationError

from graph import QueryGraphRunner
from graph.state import QueryResponse
from query.schema import StructuredQuery

from .loader import filter_queries, load_golden_dataset
from .metrics import compute_all_metrics
from .models import (
    EvaluationReport,
    GoldenDataset,
    GoldenExpected,
    GoldenQuery,
    QueryEvalResult,
)


def _check_response(
    query: GoldenQuery,
    response: QueryResponse,
    validation_failed: bool,
) -> QueryEvalResult:
    exp = query.expected
    checks: Dict[str, bool] = {}
    failures: List[str] = []
    is_known_limitation = "known-limitation" in query.tags

    if exp.should_fail_validation:
        ok = validation_failed or (response.errors and any(
            e.stage == "validate" for e in response.errors
        ))
        checks["validation_rejected"] = ok
        if not ok:
            failures.append("Expected validation to reject query but it did not")

        if exp.confidence_label_in and response.confidence_score:
            label_ok = response.confidence_score.label in exp.confidence_label_in
            checks["confidence_label"] = label_ok
            if not label_ok:
                failures.append(
                    f"Expected confidence label in {exp.confidence_label_in}, "
                    f"got {response.confidence_score.label}"
                )

        return QueryEvalResult(
            query_id=query.id,
            intent=query.intent,
            tags=query.tags,
            passed=len(failures) == 0,
            checks=checks,
            failures=failures,
            known_limitation=is_known_limitation,
        )

    if exp.intent:
        sq = response.structured_query
        actual_intent = sq.get("intent") if sq else None
        intent_ok = actual_intent == exp.intent
        checks["intent"] = intent_ok
        if not intent_ok:
            failures.append(f"Expected intent={exp.intent}, got {actual_intent}")

    if exp.status:
        node_status = response.metadata.node_status if response.metadata else {}
        if node_status.get("resolve") == "success":
            actual_status = "success"
        elif node_status.get("resolve") == "failed":
            actual_status = "not_found"
        elif node_status.get("resolve") == "skipped_document_only":
            # document_search never runs the well/SODIR resolver by
            # design - success/failure is determined by retrieve_documents.
            actual_status = "success" if node_status.get("retrieve_documents") == "success" else "not_found"
        else:
            actual_status = "not_found"

        if exp.status == "partial":
            status_ok = actual_status in ("partial", "success")
        else:
            status_ok = actual_status == exp.status
        checks["status"] = status_ok
        if not status_ok:
            failures.append(f"Expected status={exp.status}, got {actual_status}")

    if exp.min_result_count is not None:
        actual_count = response.metadata.result_count or 0
        count_ok = actual_count >= exp.min_result_count
        checks["min_result_count"] = count_ok
        if not count_ok:
            failures.append(
                f"Expected min_result_count={exp.min_result_count}, got {actual_count}"
            )

    if exp.max_result_count is not None:
        actual_count = response.metadata.result_count or 0
        count_ok = actual_count <= exp.max_result_count
        checks["max_result_count"] = count_ok
        if not count_ok:
            failures.append(
                f"Expected max_result_count={exp.max_result_count}, got {actual_count}"
            )

    if exp.sources_contain:
        actual_sources = set(response.provenance)
        missing = [s for s in exp.sources_contain if s not in actual_sources]
        src_ok = len(missing) == 0
        checks["sources_contain"] = src_ok
        if not src_ok:
            failures.append(
                f"Expected sources to contain {exp.sources_contain}, "
                f"got {list(actual_sources)}, missing {missing}"
            )

    if exp.confidence_label_in and response.confidence_score:
        label_ok = response.confidence_score.label in exp.confidence_label_in
        checks["confidence_label"] = label_ok
        if not label_ok:
            failures.append(
                f"Expected confidence label in {exp.confidence_label_in}, "
                f"got {response.confidence_score.label}"
            )

    if exp.min_document_result_count is not None:
        actual_doc_count = response.metadata.document_result_count or 0
        doc_count_ok = actual_doc_count >= exp.min_document_result_count
        checks["min_document_result_count"] = doc_count_ok
        if not doc_count_ok:
            failures.append(
                f"Expected min_document_result_count={exp.min_document_result_count}, "
                f"got {actual_doc_count}"
            )

    if "document" in query.tags and exp.min_document_result_count:
        doc_provenance_ok = "DOCUMENT" in set(response.provenance)
        checks["document_provenance_present"] = doc_provenance_ok
        if not doc_provenance_ok:
            failures.append("Expected DOCUMENT provenance for a document-tagged query but none found")

    if exp.expected_document_file_name:
        doc_file_names = {
            e.metadata.get("file_name") for e in response.evidence
            if e.entity_type == "document_chunk"
        }
        hit_ok = exp.expected_document_file_name in doc_file_names
        checks["document_hit_at_k"] = hit_ok
        if not hit_ok:
            failures.append(
                f"Expected document hit for file {exp.expected_document_file_name!r} "
                f"within top_k, got {sorted(n for n in doc_file_names if n)}"
            )

    if not exp.should_fail_validation:
        node_status = response.metadata.node_status if response.metadata else {}
        if node_status.get("resolve") == "success":
            has_evidence = len(response.evidence) > 0 or (response.metadata.result_count or 0) == 0
            checks["evidence_present"] = has_evidence
            if not has_evidence:
                failures.append("Expected evidence to be present for successful query")
        elif node_status.get("retrieve_documents") == "success":
            has_evidence = len(response.evidence) > 0 or (response.metadata.document_result_count or 0) == 0
            checks["evidence_present"] = has_evidence
            if not has_evidence:
                failures.append("Expected evidence to be present for successful document search")

        has_rationale = len(response.rationale) > 0
        checks["rationale_present"] = has_rationale
        if not has_rationale:
            failures.append("Expected rationale to be present")

        forbidden_terms = ["probably", "likely indicates", "suggests that the reservoir",
                           "I think", "in my opinion"]
        answer_lower = response.answer.lower()
        no_claims = all(term not in answer_lower for term in forbidden_terms)
        checks["no_unsupported_claims"] = no_claims
        if not no_claims:
            failures.append("Answer contains unsupported geological claims")

    return QueryEvalResult(
        query_id=query.id,
        intent=query.intent,
        tags=query.tags,
        passed=len(failures) == 0,
        checks=checks,
        failures=failures,
        known_limitation=is_known_limitation,
    )


def run_structured_evaluation(
    dataset: Optional[GoldenDataset] = None,
    *,
    intent_filter: Optional[str] = None,
    tag_filter: Optional[List[str]] = None,
    exclude_tags: Optional[List[str]] = None,
) -> EvaluationReport:
    ds = dataset or load_golden_dataset()
    queries = filter_queries(
        ds, intent=intent_filter, tags=tag_filter, exclude_tags=exclude_tags,
    )

    runner = QueryGraphRunner(use_llm=False)
    results: List[QueryEvalResult] = []

    for q in queries:
        t0 = time.perf_counter()
        validation_failed = False

        try:
            StructuredQuery.model_validate(q.structured_query)
        except (ValidationError, ValueError):
            validation_failed = True

        try:
            response = runner.run_structured_query(q.structured_query)
        except Exception as exc:
            results.append(QueryEvalResult(
                query_id=q.id,
                intent=q.intent,
                tags=q.tags,
                passed=q.expected.should_fail_validation,
                checks={},
                failures=[f"Runner exception: {exc}"],
                error=str(exc),
                known_limitation="known-limitation" in q.tags,
            ))
            continue

        elapsed = (time.perf_counter() - t0) * 1000
        result = _check_response(q, response, validation_failed)
        result.latency_ms = elapsed
        results.append(result)

    metrics = compute_all_metrics(results)
    passed = sum(1 for r in results if r.passed)
    kl_failures = sum(1 for r in results if not r.passed and r.known_limitation)

    return EvaluationReport(
        mode="structured",
        total_queries=len(results),
        passed=passed,
        failed=len(results) - passed,
        pass_rate=passed / len(results) if results else 1.0,
        metrics=metrics,
        results=results,
        known_limitation_failures=kl_failures,
        known_limitations=ds.known_limitations,
    )


def run_nl_evaluation(
    dataset: Optional[GoldenDataset] = None,
    *,
    intent_filter: Optional[str] = None,
    tag_filter: Optional[List[str]] = None,
    exclude_tags: Optional[List[str]] = None,
) -> EvaluationReport:
    ds = dataset or load_golden_dataset()
    queries = filter_queries(
        ds, intent=intent_filter, tags=tag_filter, exclude_tags=exclude_tags,
    )
    nl_queries = [q for q in queries if q.natural_language]

    runner = QueryGraphRunner(use_llm=True)
    results: List[QueryEvalResult] = []

    for q in nl_queries:
        t0 = time.perf_counter()
        try:
            response = runner.run_query(q.natural_language)
        except Exception as exc:
            results.append(QueryEvalResult(
                query_id=q.id,
                intent=q.intent,
                tags=q.tags,
                passed=False,
                checks={},
                failures=[f"Runner exception: {exc}"],
                error=str(exc),
                known_limitation="known-limitation" in q.tags,
            ))
            continue

        elapsed = (time.perf_counter() - t0) * 1000

        is_known_limitation = "known-limitation" in q.tags or (
            q.nl_expected_override and q.nl_expected_override.may_fail_dataset
        )
        checks: Dict[str, bool] = {}
        failures: List[str] = []

        exp = q.expected
        if exp.intent:
            sq = response.structured_query
            actual_intent = sq.get("intent") if sq else None
            intent_ok = actual_intent == exp.intent
            checks["intent"] = intent_ok
            if not intent_ok:
                failures.append(f"Expected intent={exp.intent}, got {actual_intent}")

        if q.nl_expected_override and q.nl_expected_override.expected_nl_dataset:
            sq = response.structured_query
            actual_ds = sq.get("target_dataset") if sq else None
            ds_ok = actual_ds == q.nl_expected_override.expected_nl_dataset
            checks["nl_dataset"] = ds_ok
            if not ds_ok:
                failures.append(
                    f"Expected NL dataset={q.nl_expected_override.expected_nl_dataset}, "
                    f"got {actual_ds}"
                )

        if exp.status:
            node_status = response.metadata.node_status if response.metadata else {}
            if node_status.get("resolve") == "success":
                actual_status = "success"
            elif node_status.get("resolve") == "failed":
                actual_status = "not_found"
            else:
                actual_status = "not_found"
            status_ok = actual_status == exp.status
            checks["status"] = status_ok
            if not status_ok:
                failures.append(f"Expected status={exp.status}, got {actual_status}")

        if exp.min_result_count is not None:
            actual_count = response.metadata.result_count or 0
            count_ok = actual_count >= exp.min_result_count
            checks["min_result_count"] = count_ok
            if not count_ok:
                failures.append(
                    f"Expected min_result_count={exp.min_result_count}, got {actual_count}"
                )

        result = QueryEvalResult(
            query_id=q.id,
            intent=q.intent,
            tags=q.tags,
            passed=len(failures) == 0,
            checks=checks,
            failures=failures,
            latency_ms=elapsed,
            known_limitation=is_known_limitation,
        )
        results.append(result)

    metrics = compute_all_metrics(results)
    passed = sum(1 for r in results if r.passed)
    kl_failures = sum(1 for r in results if not r.passed and r.known_limitation)

    return EvaluationReport(
        mode="end_to_end_nl",
        total_queries=len(results),
        passed=passed,
        failed=len(results) - passed,
        pass_rate=passed / len(results) if results else 1.0,
        metrics=metrics,
        results=results,
        known_limitation_failures=kl_failures,
        known_limitations=ds.known_limitations,
    )


def save_report(report: EvaluationReport, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        json.dump(report.model_dump(), f, indent=2, default=str)


def format_report_markdown(report: EvaluationReport) -> str:
    lines = [
        f"# Evaluation Report ({report.mode})",
        "",
        f"**Total queries:** {report.total_queries}  ",
        f"**Passed:** {report.passed}  ",
        f"**Failed:** {report.failed}  ",
        f"**Pass rate:** {report.pass_rate:.1%}  ",
        f"**Known-limitation failures:** {report.known_limitation_failures}",
        "",
    ]

    if report.known_limitations:
        lines.append("## Known Limitations")
        lines.append("")
        for kl in report.known_limitations:
            lines.append(f"- {kl}")
        lines.append("")

    lines.append("## Metrics")
    lines.append("")
    lines.append("| Metric | Value | Passed / Total |")
    lines.append("|--------|-------|----------------|")
    for m in report.metrics:
        lines.append(f"| {m.name} | {m.value:.1%} | {m.passed}/{m.total} |")
    lines.append("")

    failed_results = [r for r in report.results if not r.passed]
    if failed_results:
        lines.append("## Failed Queries")
        lines.append("")
        for r in failed_results:
            kl_tag = " **(known limitation)**" if r.known_limitation else ""
            lines.append(f"### {r.query_id}{kl_tag}")
            lines.append(f"- Intent: {r.intent}")
            lines.append(f"- Tags: {', '.join(r.tags)}")
            for f_msg in r.failures:
                lines.append(f"- FAIL: {f_msg}")
            if r.error:
                lines.append(f"- Error: {r.error}")
            lines.append("")

    passed_results = [r for r in report.results if r.passed]
    if passed_results:
        lines.append("## Passed Queries")
        lines.append("")
        lines.append("| ID | Intent | Tags | Latency (ms) |")
        lines.append("|----|--------|------|-------------|")
        for r in passed_results:
            lat = f"{r.latency_ms:.1f}" if r.latency_ms else "-"
            lines.append(f"| {r.query_id} | {r.intent} | {', '.join(r.tags)} | {lat} |")
        lines.append("")

    return "\n".join(lines)
