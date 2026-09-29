"""
Query-time LangGraph orchestration.

Wires the existing GroqInterpreter (llm/), StructuredQuery contract
(query/), and QueryResolver (resolver/) into one deterministic
interpret -> validate -> resolve -> collect_evidence ->
calculate_confidence -> generate_response pipeline. No component's logic
is duplicated here - this package only sequences existing calls and adds
a confidence heuristic and template-based final answer.
"""

from .errors import GraphError, GraphExecutionError
from .state import ConfidenceScore, EvidenceItem, ExecutionMetadata, GraphState, QueryResponse
from .workflow import QueryGraphRunner, build_graph, run_query

__all__ = [
    "QueryGraphRunner",
    "build_graph",
    "run_query",
    "GraphState",
    "QueryResponse",
    "EvidenceItem",
    "ConfidenceScore",
    "ExecutionMetadata",
    "GraphError",
    "GraphExecutionError",
]
