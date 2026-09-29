"""
Query resolver: StructuredQuery → deterministic data retrieval.

Maps validated StructuredQuery objects to actual calls against the
retrieval library (pgvector similarity) and SODIR relational data
(core/subsurface/graph schemas). No LLM, no generated SQL.
"""

from .errors import EntityNotFoundError, QueryResolutionError, ResolverDataError, UnsupportedIntentError
from .models import (
    CompanyRole,
    CompareWellsResult,
    FormationTop,
    GeologicalContextGroup,
    ResolutionResult,
    WellInfo,
    WellMatch,
    WindowMatch,
)
from .resolver import QueryResolver

__all__ = [
    "QueryResolver",
    "QueryResolutionError",
    "EntityNotFoundError",
    "UnsupportedIntentError",
    "ResolverDataError",
    "ResolutionResult",
    "WellMatch",
    "WindowMatch",
    "WellInfo",
    "FormationTop",
    "CompareWellsResult",
    "GeologicalContextGroup",
    "CompanyRole",
]
