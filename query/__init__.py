"""
Structured query contract for the future LLM layer (docs/query_contract.md).

No SQL, no table names, no executable code - just a small, validated,
deterministic schema an eventual LLM's output gets parsed into. Nothing in
this package connects to Gemini, PostgreSQL, pgvector, or LangGraph.
"""

from .schema import (
    DatasetEnum,
    GeologicalContextField,
    OutputField,
    QueryIntent,
    StructuredQuery,
)
from .validator import (
    QueryValidationError,
    describe_errors,
    is_valid,
    validate_batch,
    validate_query,
)

__all__ = [
    "DatasetEnum",
    "GeologicalContextField",
    "OutputField",
    "QueryIntent",
    "StructuredQuery",
    "QueryValidationError",
    "describe_errors",
    "is_valid",
    "validate_batch",
    "validate_query",
]
