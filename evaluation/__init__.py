"""Evaluation framework for the geological intelligence query system."""

from .loader import filter_queries, load_golden_dataset
from .metrics import compute_all_metrics
from .models import (
    EvaluationReport,
    GoldenDataset,
    GoldenExpected,
    GoldenQuery,
    MetricResult,
    NLExpectedOverride,
    QueryEvalResult,
)
from .runner import (
    format_report_markdown,
    run_nl_evaluation,
    run_structured_evaluation,
    save_report,
)

__all__ = [
    "load_golden_dataset",
    "filter_queries",
    "compute_all_metrics",
    "run_structured_evaluation",
    "run_nl_evaluation",
    "save_report",
    "format_report_markdown",
    "GoldenDataset",
    "GoldenQuery",
    "GoldenExpected",
    "NLExpectedOverride",
    "EvaluationReport",
    "MetricResult",
    "QueryEvalResult",
]
