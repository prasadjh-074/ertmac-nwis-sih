"""
LangGraph workflow wiring: builds the query-time StateGraph and exposes
run_query() / run_structured_query() as the public entry points.

Why LangGraph here:
- Orchestration: 7 fixed stages (interpret -> validate -> resolve ->
  collect_evidence -> retrieve_documents -> calculate_confidence ->
  generate_response, with fuse_evidence between retrieve_documents and
  calculate_confidence) need one explicit place that sequences them,
  instead of a chain of ad-hoc function calls scattered across callers.
- Explicit state: every intermediate artifact (structured query,
  resolution result, evidence, confidence) is a named, inspectable field
  on GraphState rather than a local variable buried in a call stack.
- Controlled execution: conditional edges make failure paths (invalid
  query, resolver error) first-class routes instead of exceptions that
  abort the whole run - see route_after_interpret/route_after_validate.
- Future extension: this graph is a single linear path today (no
  autonomous agents, no branching LLM decisions, no tool-calling loop);
  the same StateGraph scaffold is where a later stage could add
  clarification loops or multi-step retrieval WITHOUT changing
  interpret/validate/resolve themselves.
"""

from __future__ import annotations

import time
from typing import Optional

from langgraph.graph import END, START, StateGraph

from llm.groq_interpreter import GroqInterpreter
from query.schema import StructuredQuery
from resolver.resolver import QueryResolver

from .nodes import (
    ResolverFactory,
    assess_risk_node,
    calculate_confidence_node,
    collect_evidence_node,
    fuse_evidence_node,
    generate_alerts_node,
    generate_response_node,
    make_interpret_node,
    make_resolve_node,
    retrieve_documents_node,
    route_after_interpret,
    route_after_validate,
    validate_node,
)
from .state import ExecutionMetadata, GraphState, QueryResponse


def build_graph(interpreter: Optional[GroqInterpreter], resolver_factory: ResolverFactory):
    """Assembles the StateGraph described in docs/query_graph.md. Pure
    wiring - no business logic lives here, only which node runs after
    which and under what condition."""

    workflow = StateGraph(GraphState)

    workflow.add_node("interpret", make_interpret_node(interpreter))
    workflow.add_node("validate", validate_node)
    workflow.add_node("resolve", make_resolve_node(resolver_factory))
    workflow.add_node("collect_evidence", collect_evidence_node)
    workflow.add_node("retrieve_documents", retrieve_documents_node)
    workflow.add_node("fuse_evidence", fuse_evidence_node)
    workflow.add_node("assess_risk", assess_risk_node)
    workflow.add_node("generate_alerts", generate_alerts_node)
    workflow.add_node("calculate_confidence", calculate_confidence_node)
    workflow.add_node("generate_response", generate_response_node)

    workflow.add_edge(START, "interpret")
    workflow.add_conditional_edges("interpret", route_after_interpret, {
        "validate": "validate",
        "collect_evidence": "collect_evidence",
    })
    workflow.add_conditional_edges("validate", route_after_validate, {
        "resolve": "resolve",
        "collect_evidence": "collect_evidence",
    })
    workflow.add_edge("resolve", "collect_evidence")
    workflow.add_edge("collect_evidence", "retrieve_documents")
    workflow.add_edge("retrieve_documents", "fuse_evidence")
    workflow.add_edge("fuse_evidence", "assess_risk")
    workflow.add_edge("assess_risk", "generate_alerts")
    workflow.add_edge("generate_alerts", "calculate_confidence")
    workflow.add_edge("calculate_confidence", "generate_response")
    workflow.add_edge("generate_response", END)

    return workflow.compile()


class QueryGraphRunner:
    """Owns the compiled graph plus the (optional) GroqInterpreter and the
    QueryResolver factory. Neither is stored in graph state - only passed
    into node closures at build time - so GraphState stays plain data, per
    the "no mutable service objects in state" constraint.
    """

    def __init__(
        self,
        interpreter: Optional[GroqInterpreter] = None,
        resolver_factory: Optional[ResolverFactory] = None,
        use_llm: bool = True,
    ):
        if interpreter is None and use_llm:
            interpreter = GroqInterpreter()
        self._interpreter = interpreter if use_llm else None
        self._resolver_factory: ResolverFactory = resolver_factory or QueryResolver
        self._graph = build_graph(self._interpreter, self._resolver_factory)

    def run_query(self, question: str) -> QueryResponse:
        """Full pipeline: natural language -> GroqInterpreter -> ... -> QueryResponse."""
        return self._run(user_question=question, structured_query=None)

    def run_structured_query(self, structured_query) -> QueryResponse:
        """Deterministic entry point that bypasses Groq entirely.

        The caller supplies an already-built StructuredQuery (or an
        equivalent dict); the graph runs validate -> resolve ->
        collect_evidence -> calculate_confidence -> generate_response
        exactly as it would for an LLM-interpreted question, with
        execution_metadata.llm_used left False. This is what
        examples/query_graph_demo.py falls back to when no Groq API key
        is configured, and what graph unit tests use to avoid requiring
        live Groq access.
        """
        return self._run(user_question="", structured_query=structured_query)

    def _run(self, user_question: str, structured_query) -> QueryResponse:
        start = time.monotonic()
        initial_state: GraphState = {
            "user_question": user_question,
            "structured_query": structured_query,
            "interpretation_result": None,
            "resolution_result": None,
            "evidence": [],
            "fused_evidence": None,
            "confidence": None,
            "rationale": [],
            "final_answer": None,
            "errors": [],
            "execution_metadata": ExecutionMetadata(),
            "risk_assessments": None,
            "rule_results": None,
            "alerts": None,
        }

        final_state = self._graph.invoke(initial_state)

        meta: ExecutionMetadata = final_state.get("execution_metadata") or ExecutionMetadata()
        meta.total_execution_ms = (time.monotonic() - start) * 1000

        sq = final_state.get("structured_query")
        sq_dict = sq.model_dump(mode="json", exclude_none=True) if isinstance(sq, StructuredQuery) else sq

        resolution = final_state.get("resolution_result")
        provenance = list(resolution.sources) if resolution is not None else []

        # Append any additional source systems fuse_evidence discovered
        # (e.g. "DOCUMENT" for document_search or a combined query) that
        # aren't already covered by resolution.sources - never replaces
        # the well/SODIR provenance already established above.
        fused = final_state.get("fused_evidence")
        if fused is not None:
            for source in fused.source_systems:
                if source not in provenance:
                    provenance.append(source)

        return QueryResponse(
            answer=final_state.get("final_answer") or "",
            structured_query=sq_dict,
            evidence=final_state.get("evidence", []),
            confidence_score=final_state.get("confidence"),
            rationale=final_state.get("rationale", []),
            provenance=provenance,
            metadata=meta,
            errors=final_state.get("errors", []),
            risk_assessments=final_state.get("risk_assessments") or [],
            alerts=final_state.get("alerts") or [],
        )


def run_query(
    question: str,
    interpreter: Optional[GroqInterpreter] = None,
    resolver_factory: Optional[ResolverFactory] = None,
) -> QueryResponse:
    """Module-level convenience wrapper: builds a QueryGraphRunner and runs
    one question. For repeated queries, construct QueryGraphRunner
    directly so the compiled graph is reused."""

    runner = QueryGraphRunner(interpreter=interpreter, resolver_factory=resolver_factory)
    return runner.run_query(question)
