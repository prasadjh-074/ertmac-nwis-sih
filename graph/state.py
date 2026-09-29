"""
Typed state and supporting result models for the query-time graph.

GraphState deliberately holds only plain data (strings, pydantic models,
dicts, lists, dataclasses) - no database connections, no
GroqInterpreter/QueryResolver instances. Those live on QueryGraphRunner
(workflow.py) and are passed into node closures at graph-build time, never
placed into the state dict itself.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, TypedDict, Union

from pydantic import BaseModel, Field

from llm.groq_interpreter import InterpretationResult
from query.schema import StructuredQuery
from resolver.models import ResolutionResult

from .errors import GraphError


class EvidenceItem(BaseModel):
    """One normalized piece of evidence backing the final answer.

    Preserves provenance across the three underlying systems
    (FORCE_2020, VOLVE, SODIR) - never collapsed into an indistinguishable
    source. Built only from fields already present in ResolutionResult;
    nothing here is invented.
    """

    source_system: str
    entity_type: str
    well_id: Optional[str] = None
    source_id: Optional[str] = None
    similarity: Optional[float] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ConfidenceScore(BaseModel):
    """A deterministic, heuristic confidence indicator - explicitly NOT a
    calibrated statistical probability. See docs/query_graph.md and
    graph/nodes.py::calculate_confidence_node for the full formula."""

    value: float
    label: str
    factors: Dict[str, Any] = Field(default_factory=dict)
    basis: List[str] = Field(default_factory=list)
    note: str = "Heuristic confidence indicator, not a calibrated probability."
    is_probability: bool = False


class ExecutionMetadata(BaseModel):
    """Observability metadata for one graph run. Never holds API keys or
    credentials - only counts, timings, and node status strings."""

    total_execution_ms: Optional[float] = None
    intent: Optional[str] = None
    result_count: Optional[int] = None
    data_sources: List[str] = Field(default_factory=list)
    llm_used: bool = False
    node_status: Dict[str, str] = Field(default_factory=dict)
    # Document retrieval result count, tracked separately from
    # result_count (which reflects only well/SODIR resolution) so a
    # combined query's well and document counts are never conflated.
    document_result_count: Optional[int] = None


class QueryResponse(BaseModel):
    """Public result of QueryGraphRunner.run_query() / run_structured_query()."""

    answer: str
    structured_query: Optional[Dict[str, Any]] = None
    evidence: List[EvidenceItem] = Field(default_factory=list)
    confidence_score: Optional[ConfidenceScore] = None
    rationale: List[str] = Field(default_factory=list)
    provenance: List[str] = Field(default_factory=list)
    metadata: ExecutionMetadata = Field(default_factory=ExecutionMetadata)
    errors: List[GraphError] = Field(default_factory=list)
    risk_assessments: List[Any] = Field(default_factory=list)
    alerts: List[Any] = Field(default_factory=list)


class GraphState(TypedDict, total=False):
    """LangGraph state for a single user query."""

    user_question: str
    # dict (caller-supplied, pre-validation) or StructuredQuery (post-validation/post-interpretation)
    structured_query: Optional[Union[StructuredQuery, Dict[str, Any]]]
    interpretation_result: Optional[InterpretationResult]
    resolution_result: Optional[ResolutionResult]
    evidence: List[EvidenceItem]
    fused_evidence: Optional[Any]
    confidence: Optional[ConfidenceScore]
    rationale: List[str]
    final_answer: Optional[str]
    errors: List[GraphError]
    execution_metadata: ExecutionMetadata
    # Phase 3: risk intelligence
    risk_assessments: Optional[List[Any]]
    rule_results: Optional[List[Any]]
    alerts: Optional[List[Any]]
