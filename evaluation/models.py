"""Typed models for the evaluation framework."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class GoldenExpected(BaseModel):
    """Expected outcomes for a golden query."""

    intent: Optional[str] = None
    status: Optional[str] = None
    min_result_count: Optional[int] = None
    max_result_count: Optional[int] = None
    sources_contain: Optional[List[str]] = None
    confidence_label_in: Optional[List[str]] = None
    should_fail_validation: bool = False
    result_contains: Optional[Dict[str, Any]] = None
    # Document retrieval expectations (384-dim chunk space, tracked
    # separately from min_result_count/max_result_count which reflect
    # well/SODIR resolution only).
    min_document_result_count: Optional[int] = None
    expected_document_file_name: Optional[str] = None


class NLExpectedOverride(BaseModel):
    """NL-specific expectations that may differ from structured evaluation."""

    note: Optional[str] = None
    expected_nl_intent: Optional[str] = None
    expected_nl_dataset: Optional[str] = None
    may_fail_dataset: bool = False


class GoldenQuery(BaseModel):
    """A single golden evaluation query."""

    id: str
    intent: str
    description: str
    tags: List[str] = Field(default_factory=list)
    natural_language: Optional[str] = None
    structured_query: Dict[str, Any]
    expected: GoldenExpected
    nl_expected_override: Optional[NLExpectedOverride] = None


class GoldenDataset(BaseModel):
    """Top-level container for the golden query dataset."""

    version: str
    description: str
    known_limitations: List[str] = Field(default_factory=list)
    queries: List[GoldenQuery]


class MetricResult(BaseModel):
    """One evaluated metric."""

    name: str
    value: float
    total: int
    passed: int
    details: List[str] = Field(default_factory=list)


class QueryEvalResult(BaseModel):
    """Evaluation outcome for a single golden query."""

    query_id: str
    intent: str
    tags: List[str] = Field(default_factory=list)
    passed: bool
    checks: Dict[str, bool] = Field(default_factory=dict)
    failures: List[str] = Field(default_factory=list)
    latency_ms: Optional[float] = None
    known_limitation: bool = False
    error: Optional[str] = None


class EvaluationReport(BaseModel):
    """Aggregate evaluation report."""

    mode: str
    total_queries: int
    passed: int
    failed: int
    pass_rate: float
    metrics: List[MetricResult] = Field(default_factory=list)
    results: List[QueryEvalResult] = Field(default_factory=list)
    known_limitation_failures: int = 0
    known_limitations: List[str] = Field(default_factory=list)
