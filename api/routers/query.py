"""Query router — the LangGraph-backed query pipeline exposed over HTTP.

  POST /query             — natural-language question (requires LLM)
  POST /query/structured  — validated StructuredQuery (no LLM required)

The structured endpoint is the deterministic contract every client
should prefer.  It never invokes the LLM, so it works even when
GROQ_API_KEY is not configured — matching the production stance that
the LLM is optional and never on the critical path.

Security invariants (already enforced by lower layers, restated here
for clarity):

  * StructuredQuery has ``extra="forbid"`` and every field is an enum,
    a regex-validated string, or a bounded int/float.  The LLM cannot
    produce raw SQL.
  * All SQL below the resolver uses parameterized placeholders.
  * The natural-language endpoint never echoes the user's question
    into a SQL string — it goes through the interpreter which emits a
    StructuredQuery, which then routes to the same code paths as the
    structured endpoint.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from query.schema import StructuredQuery

from ..deps import get_graph_runner

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/query", tags=["query"])


class NLQueryRequest(BaseModel):
    """Natural-language question payload."""
    question: str = Field(..., min_length=1, max_length=1000)


class StructuredQueryRequest(BaseModel):
    """Structured-query payload — a StructuredQuery, or its plain
    dict form (the graph accepts either)."""
    structured_query: Dict[str, Any]


class QueryResponseBody(BaseModel):
    """Public response for both /query and /query/structured.

    Mirrors graph.state.QueryResponse but with model_dump()ed
    subfields so this router doesn't leak internal dataclasses to
    HTTP clients (Pydantic's arbitrary_types_allowed is disabled by
    default to prevent that).
    """
    answer: str
    structured_query: Optional[Dict[str, Any]] = None
    evidence: List[Dict[str, Any]] = Field(default_factory=list)
    confidence_score: Optional[Dict[str, Any]] = None
    rationale: List[str] = Field(default_factory=list)
    provenance: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    errors: List[Dict[str, Any]] = Field(default_factory=list)
    risk_assessments: List[Dict[str, Any]] = Field(default_factory=list)
    alerts: List[Dict[str, Any]] = Field(default_factory=list)


def _to_dict(obj: Any) -> Any:
    """Coerce dataclasses / pydantic models / plain values to a JSON-safe form."""
    if obj is None:
        return None
    if isinstance(obj, (str, int, float, bool)):
        return obj
    if hasattr(obj, "model_dump"):
        return obj.model_dump(mode="json", exclude_none=True)
    if hasattr(obj, "__dataclass_fields__"):
        from dataclasses import asdict

        return _to_dict(asdict(obj))
    if isinstance(obj, dict):
        return {k: _to_dict(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_to_dict(x) for x in obj]
    return str(obj)


def _serialise_query_response(qr) -> QueryResponseBody:
    return QueryResponseBody(
        answer=qr.answer or "",
        structured_query=qr.structured_query,
        evidence=[_to_dict(e) for e in (qr.evidence or [])],
        confidence_score=_to_dict(qr.confidence_score) if qr.confidence_score else None,
        rationale=list(qr.rationale or []),
        provenance=list(qr.provenance or []),
        metadata=_to_dict(qr.metadata) or {},
        errors=[_to_dict(e) for e in (qr.errors or [])],
        risk_assessments=[_to_dict(r) for r in (qr.risk_assessments or [])],
        alerts=[_to_dict(a) for a in (qr.alerts or [])],
    )


@router.post("", response_model=QueryResponseBody)
def natural_language_query(
    body: NLQueryRequest,
    runner=Depends(get_graph_runner),
):
    """Natural-language query.  Requires a configured LLM (GROQ_API_KEY).

    When the LLM is disabled, this endpoint returns 503 with an
    ``llm_unavailable`` slug — clients should fall back to the
    /query/structured endpoint.
    """
    if runner is None:
        raise HTTPException(
            status_code=503,
            detail="LLM interpretation is not configured on this server. "
                   "Use POST /query/structured for deterministic queries.",
        )
    try:
        qr = runner.run_query(body.question)
    except Exception as exc:
        logger.exception("run_query failed: %s", exc)
        raise HTTPException(status_code=500, detail="query execution failed")
    return _serialise_query_response(qr)


@router.post("/structured", response_model=QueryResponseBody)
def structured_query(body: StructuredQueryRequest):
    """Deterministic query entry point — bypasses the LLM entirely.

    The payload's ``structured_query`` is validated against
    ``StructuredQuery`` (``extra='forbid'``, every field bounded); any
    unknown / invalid field is rejected with a 422 before any DB call
    or vector-search runs.
    """
    try:
        sq = StructuredQuery.model_validate(body.structured_query)
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"invalid structured_query: {exc}")

    # Import lazily so a machine without langgraph/groq installed can
    # still import this router (only the endpoint call requires the graph).
    from graph.workflow import QueryGraphRunner

    runner = QueryGraphRunner(use_llm=False)
    try:
        qr = runner.run_structured_query(sq)
    except Exception as exc:
        logger.exception("run_structured_query failed: %s", exc)
        raise HTTPException(status_code=500, detail="query execution failed")
    return _serialise_query_response(qr)
