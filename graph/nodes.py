"""
Node implementations for the query-time LangGraph.

Each node function is a thin adapter around exactly one existing
component (GroqInterpreter, query.validate_query, QueryResolver). No node
re-implements interpretation, validation, resolution, or vector-search
logic - those all remain the single source of truth in llm/, query/, and
resolver/ respectively.
"""

from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional

from llm.groq_interpreter import GroqInterpreter, InterpretationError
from query.schema import QueryIntent, StructuredQuery
from query.validator import QueryValidationError, validate_query
from resolver.errors import QueryResolutionError
from resolver.resolver import QueryResolver

from .errors import GraphError
from .state import ConfidenceScore, EvidenceItem, ExecutionMetadata, GraphState

ResolverFactory = Callable[[], QueryResolver]


# ============================================================
# 1. interpret
# ============================================================

def make_interpret_node(interpreter: Optional[GroqInterpreter]):
    """Builds the interpret node bound to one GroqInterpreter instance (or
    None, for the deterministic demo/test mode).

    If the caller already placed a StructuredQuery (or an equivalent dict)
    into state['structured_query'] before invoking the graph, this node is
    a pass-through - no LLM call is made, and execution_metadata.llm_used
    stays False. This is what run_structured_query() relies on.

    Otherwise, calls the existing GroqInterpreter.interpret() - no second
    LLM client is created here.
    """

    def _interpret(state: GraphState) -> Dict[str, Any]:
        errors = list(state.get("errors", []))
        meta = state.get("execution_metadata") or ExecutionMetadata()

        if state.get("structured_query") is not None:
            meta.llm_used = False
            meta.node_status["interpret"] = "skipped_preset"
            return {"execution_metadata": meta}

        if interpreter is None:
            errors.append(GraphError(
                stage="interpret", error_type="ConfigurationError",
                message="No GroqInterpreter configured and no structured_query was pre-supplied.",
            ))
            meta.node_status["interpret"] = "failed"
            return {"errors": errors, "execution_metadata": meta}

        question = state.get("user_question", "")
        try:
            result = interpreter.interpret(question)
        except InterpretationError as exc:
            errors.append(GraphError(
                stage="interpret", error_type="InterpretationError", message=str(exc),
            ))
            meta.llm_used = True
            meta.node_status["interpret"] = "failed"
            return {"errors": errors, "execution_metadata": meta}

        meta.llm_used = True
        meta.node_status["interpret"] = "success"
        return {
            "interpretation_result": result,
            "structured_query": result.query,
            "execution_metadata": meta,
        }

    return _interpret


def route_after_interpret(state: GraphState) -> str:
    """On interpretation failure, skip straight to collect_evidence rather
    than all the way to generate_response - collect_evidence/
    calculate_confidence both handle a missing resolution_result cleanly
    (empty evidence, confidence 0.0/"none"), so confidence_score is always
    populated instead of sometimes being left as None."""
    return "validate" if state.get("structured_query") is not None else "collect_evidence"


# ============================================================
# 2. validate
# ============================================================

def validate_node(state: GraphState) -> Dict[str, Any]:
    """Re-validates whatever is in structured_query using the existing
    StructuredQuery contract (query.validate_query) - the single
    validation system in this project. This also normalizes a
    caller-supplied raw dict (demo/test mode) into a StructuredQuery
    instance, so resolve() always receives a real StructuredQuery.

    If invalid: records a structured error and clears structured_query,
    which routes the graph straight to generate_response - PostgreSQL and
    retrieval are never touched for an invalid query.
    """

    errors = list(state.get("errors", []))
    meta = state.get("execution_metadata") or ExecutionMetadata()
    candidate = state.get("structured_query")

    if candidate is None:
        meta.node_status["validate"] = "skipped"
        return {"execution_metadata": meta}

    if isinstance(candidate, StructuredQuery):
        data = candidate.model_dump(mode="json", exclude_none=True)
    else:
        data = candidate

    try:
        validated = validate_query(data)
    except QueryValidationError as exc:
        errors.append(GraphError(
            stage="validate", error_type="QueryValidationError",
            message="; ".join(exc.errors),
        ))
        meta.node_status["validate"] = "failed"
        return {"structured_query": None, "errors": errors, "execution_metadata": meta}

    meta.intent = validated.intent.value
    meta.node_status["validate"] = "success"
    return {"structured_query": validated, "execution_metadata": meta}


def route_after_validate(state: GraphState) -> str:
    """On validation failure, skip resolve (never touch PostgreSQL/
    retrieval for an invalid query) but still run collect_evidence /
    calculate_confidence so confidence_score is always populated."""
    return "resolve" if isinstance(state.get("structured_query"), StructuredQuery) else "collect_evidence"


# ============================================================
# 3. resolve
# ============================================================

def make_resolve_node(resolver_factory: ResolverFactory):
    """resolver_factory builds a QueryResolver (default: QueryResolver
    itself, which opens its own PostgreSQL connection on first use). It is
    called once per graph run; the resolver is closed afterwards. Never
    stored in graph state - it lives only for the duration of this node's
    call, per the "no mutable service objects in state" constraint.
    """

    def _resolve(state: GraphState) -> Dict[str, Any]:
        errors = list(state.get("errors", []))
        meta = state.get("execution_metadata") or ExecutionMetadata()
        query = state.get("structured_query")

        if not isinstance(query, StructuredQuery):
            meta.node_status["resolve"] = "skipped"
            return {"execution_metadata": meta}

        if query.intent == QueryIntent.DOCUMENT_SEARCH:
            # document_search is document-only - it never touches the
            # well/SODIR resolver. retrieve_documents_node (after
            # collect_evidence) handles it entirely.
            meta.node_status["resolve"] = "skipped_document_only"
            return {"execution_metadata": meta}

        resolver = resolver_factory()
        try:
            result = resolver.resolve(query)
        except QueryResolutionError as exc:
            errors.append(GraphError(
                stage="resolve", error_type=type(exc).__name__, message=str(exc),
            ))
            meta.node_status["resolve"] = "failed"
            return {"errors": errors, "execution_metadata": meta, "resolution_result": None}
        finally:
            close = getattr(resolver, "close", None)
            if callable(close):
                close()

        meta.result_count = result.result_count
        meta.data_sources = result.sources
        meta.node_status["resolve"] = "success"
        return {"resolution_result": result, "execution_metadata": meta}

    return _resolve


# ============================================================
# 4. collect_evidence
# ============================================================

def collect_evidence_node(state: GraphState) -> Dict[str, Any]:
    """Builds a normalized EvidenceItem list from ResolutionResult.results.

    Never invents evidence: if resolution_result is None, or a given
    result group is empty, the corresponding evidence is simply absent.
    Provenance (FORCE_2020 / VOLVE / SODIR) is read directly from each
    result record's own dataset/source_system field, never guessed or
    collapsed across systems.
    """

    meta = state.get("execution_metadata") or ExecutionMetadata()
    result = state.get("resolution_result")

    if result is None:
        meta.node_status["collect_evidence"] = "skipped"
        return {"evidence": [], "execution_metadata": meta}

    evidence: List[EvidenceItem] = []
    intent = result.intent
    query_meta = result.query if isinstance(result.query, dict) else {}
    target_well_id = query_meta.get("target_well_id")

    if intent == "similar_wells":
        for r in (result.results or []):
            evidence.append(EvidenceItem(
                source_system=r.get("dataset", "unknown"),
                entity_type="well",
                well_id=r.get("well_id"),
                similarity=r.get("similarity"),
                metadata={k: v for k, v in r.items() if k not in ("dataset", "well_id", "similarity")},
            ))

    elif intent == "similar_windows":
        for r in (result.results or []):
            evidence.append(EvidenceItem(
                source_system=r.get("dataset", "unknown"),
                entity_type="window",
                well_id=r.get("well_id"),
                source_id=str(r["window_id"]) if r.get("window_id") is not None else None,
                similarity=r.get("similarity"),
                metadata={k: v for k, v in r.items() if k not in ("dataset", "well_id", "window_id", "similarity")},
            ))

    elif intent == "well_information":
        r = result.results or {}
        evidence.append(EvidenceItem(
            source_system=r.get("source_system", r.get("dataset", "unknown")),
            entity_type="well_info",
            well_id=r.get("well_id"),
            source_id=str(r["sodir_wellbore_id"]) if r.get("sodir_wellbore_id") is not None else None,
            metadata={k: v for k, v in r.items() if k not in ("source_system", "well_id", "sodir_wellbore_id")},
        ))

    elif intent == "formation_information":
        for r in (result.results or []):
            evidence.append(EvidenceItem(
                source_system=r.get("source_system", "SODIR"),
                entity_type="formation",
                well_id=target_well_id,
                source_id=str(r["formation_id"]) if r.get("formation_id") is not None else None,
                metadata={k: v for k, v in r.items() if k not in ("source_system", "formation_id")},
            ))

    elif intent == "compare_wells":
        r = result.results or {}
        for label in ("target", "comparison"):
            info = r.get(label) or {}
            evidence.append(EvidenceItem(
                source_system=info.get("source_system", info.get("dataset", "unknown")),
                entity_type="well_info",
                well_id=info.get("well_id"),
                source_id=str(info["sodir_wellbore_id"]) if info.get("sodir_wellbore_id") is not None else None,
                metadata={k: v for k, v in info.items() if k not in ("source_system", "well_id", "sodir_wellbore_id")},
            ))
        if r.get("similarity") is not None:
            evidence.append(EvidenceItem(
                source_system="geointelligence",
                entity_type="similarity_score",
                similarity=r["similarity"],
                metadata={
                    "target_well_id": (r.get("target") or {}).get("well_id"),
                    "comparison_well_id": (r.get("comparison") or {}).get("well_id"),
                },
            ))

    elif intent == "geological_context":
        for group in (result.results or []):
            entity_type = group.get("entity_type", "unknown")
            source_system = group.get("source_system", "SODIR")
            for record in group.get("records", []):
                evidence.append(EvidenceItem(
                    source_system=source_system,
                    entity_type=entity_type,
                    well_id=target_well_id,
                    metadata=record,
                ))

    meta.node_status["collect_evidence"] = "success"
    return {"evidence": evidence, "execution_metadata": meta}


# ============================================================
# 4a. retrieve_documents
# ============================================================

def retrieve_documents_node(state: GraphState) -> Dict[str, Any]:
    """Semantic search over ingested document chunks (384-dim
    sentence-transformer embeddings) - a COMPLETELY SEPARATE vector space
    from the 30-dim well/window embeddings used by collect_evidence.

    Runs whenever structured_query.search_text is set, regardless of
    intent: document_search (document-only) or any well/SODIR intent with
    search_text also set (a "combined" query) both trigger this node.
    Appends document evidence onto whatever collect_evidence already
    produced - it never overwrites well evidence.
    """

    errors = list(state.get("errors", []))
    meta = state.get("execution_metadata") or ExecutionMetadata()
    query = state.get("structured_query")
    evidence = list(state.get("evidence", []))

    if not isinstance(query, StructuredQuery) or not query.search_text:
        meta.node_status["retrieve_documents"] = "skipped"
        return {"execution_metadata": meta}

    from document_retrieval.search import search_documents

    try:
        results = search_documents(
            query_text=query.search_text,
            top_k=query.top_k or 5,
            source_type=query.document_source_type.value if query.document_source_type else None,
            file_name=query.document_file_name,
        )
    except Exception as exc:
        errors.append(GraphError(
            stage="retrieve_documents", error_type=type(exc).__name__, message=str(exc),
        ))
        meta.node_status["retrieve_documents"] = "failed"
        return {"errors": errors, "execution_metadata": meta}

    for r in results:
        evidence.append(EvidenceItem(
            source_system="DOCUMENT",
            entity_type="document_chunk",
            well_id=None,
            source_id=r.chunk_id,
            similarity=r.similarity,
            metadata={
                "document_id": r.document_id,
                "file_name": r.file_name,
                "page_number": r.page_number,
                "chunk_index": r.chunk_index,
                "section": r.section,
                "text": r.text,
            },
        ))

    meta.document_result_count = len(results)
    meta.node_status["retrieve_documents"] = "success"
    return {"evidence": evidence, "execution_metadata": meta}


# ============================================================
# 4b. fuse_evidence
# ============================================================

def fuse_evidence_node(state: GraphState) -> Dict[str, Any]:
    """Runs deterministic evidence fusion over the collected EvidenceItems.
    Produces FusedEvidence with deduplication, grouping, provenance,
    conflict detection, and missing-information tracking. No LLM is used.
    """
    from evidence.fusion import fuse_evidence as _fuse

    meta = state.get("execution_metadata") or ExecutionMetadata()
    evidence = state.get("evidence", [])
    resolution = state.get("resolution_result")
    intent = meta.intent

    fused = _fuse(evidence, resolution, intent)
    meta.node_status["fuse_evidence"] = "success"
    return {"fused_evidence": fused, "execution_metadata": meta}


# ============================================================
# 5. calculate_confidence
# ============================================================

def calculate_confidence_node(state: GraphState) -> Dict[str, Any]:
    """Deterministic, heuristic confidence indicator - NOT a calibrated
    statistical probability. See docs/query_graph.md for the rationale.

    confidence_score.value = weighted sum of four components, each in [0, 1]:

      status_component      (weight 0.40): 1.0 if ResolutionResult.status
                             == "success", 0.5 if "partial", 0.0 if
                             "not_found" or no resolution was reached.

      presence_component    (weight 0.30): 1.0 if result_count > 0, else 0.0.

      similarity_component  (weight 0.20): mean similarity across any
                             result records that carry one (similar_wells,
                             similar_windows, compare_wells). 0.0 if the
                             intent has similarity but none was found;
                             0.5 (neutral, "not applicable") for intents
                             with no similarity concept at all
                             (well_information, formation_information,
                             geological_context).

      provenance_component  (weight 0.10): 1.0 if results were backed by
                             2+ distinct source systems (e.g. a dataset
                             plus SODIR), 0.5 if exactly one, 0.0 if none.

    If interpretation or validation failed before the resolver ever ran,
    the score is fixed at 0.0 with label "none" - there is nothing to be
    confident about.

    label: "high" if value >= 0.75, "medium" if value >= 0.4, else "low"
    (or "none" for the pre-resolve-failure case above).
    """

    errors = state.get("errors", [])
    meta = state.get("execution_metadata") or ExecutionMetadata()
    result = state.get("resolution_result")

    pre_resolve_failed = any(e.stage in ("interpret", "validate") for e in errors)
    retrieve_documents_failed = any(e.stage == "retrieve_documents" for e in errors)

    fused = state.get("fused_evidence")

    if pre_resolve_failed:
        score = ConfidenceScore(
            value=0.0, label="none",
            factors={"reason": "query never reached the resolver"},
            basis=["query never reached the resolver"],
        )
        meta.node_status["calculate_confidence"] = "success"
        return {"confidence": score, "execution_metadata": meta}

    if meta.intent == "document_search":
        # document_search never produces a ResolutionResult (result is
        # always None here by design - see make_resolve_node) - confidence
        # is computed from document evidence alone, using the SAME
        # weighted formula shape as the well-based path below, but with
        # document-only components. Never blended with well similarity.
        if retrieve_documents_failed:
            score = ConfidenceScore(
                value=0.0, label="none",
                factors={"reason": "document retrieval failed"},
                basis=["document retrieval failed"],
            )
            meta.node_status["calculate_confidence"] = "success"
            return {"confidence": score, "execution_metadata": meta}

        doc_items = [i for i in (fused.items if fused else []) if i.source_type == "document"]
        status_component = 1.0
        presence_component = 1.0 if doc_items else 0.0
        doc_sims = [i.similarity for i in doc_items if i.similarity is not None]
        similarity_component = (sum(doc_sims) / len(doc_sims)) if doc_sims else 0.0
        file_names = {
            i.value.get("file_name") for i in doc_items
            if isinstance(i.value, dict) and i.value.get("file_name")
        }
        provenance_component = 1.0 if len(file_names) >= 2 else (0.5 if len(file_names) == 1 else 0.0)

        value = (
            0.40 * status_component
            + 0.30 * presence_component
            + 0.20 * similarity_component
            + 0.10 * provenance_component
        )
        value = max(0.0, min(1.0, value))
        label = "high" if value >= 0.75 else "medium" if value >= 0.4 else "low"

        factors = {
            "status_component": status_component,
            "presence_component": presence_component,
            "similarity_component": round(similarity_component, 3),
            "provenance_component": provenance_component,
            "result_count": len(doc_items),
            "sources": sorted(file_names),
            "document_search": True,
        }
        from evidence.rationale import generate_confidence_basis as _gen_basis_doc
        basis = _gen_basis_doc(factors, fused) if fused else []
        score = ConfidenceScore(value=round(value, 3), label=label, factors=factors, basis=basis)
        meta.node_status["calculate_confidence"] = "success"
        return {"confidence": score, "execution_metadata": meta}

    if result is None:
        score = ConfidenceScore(
            value=0.0, label="none",
            factors={"reason": "query never reached the resolver"},
            basis=["query never reached the resolver"],
        )
        meta.node_status["calculate_confidence"] = "success"
        return {"confidence": score, "execution_metadata": meta}

    status_component = {"success": 1.0, "partial": 0.5, "not_found": 0.0}.get(result.status, 0.0)
    presence_component = 1.0 if result.result_count > 0 else 0.0

    similarities: List[float] = []
    if isinstance(result.results, list):
        for r in result.results:
            if isinstance(r, dict) and r.get("similarity") is not None:
                similarities.append(r["similarity"])
    elif isinstance(result.results, dict):
        if result.results.get("similarity") is not None:
            similarities.append(result.results["similarity"])

    has_similarity_concept = result.intent in ("similar_wells", "similar_windows", "compare_wells")
    if similarities:
        similarity_component = sum(similarities) / len(similarities)
    elif has_similarity_concept:
        similarity_component = 0.0
    else:
        similarity_component = 0.5

    n_sources = len(set(result.sources))
    provenance_component = 1.0 if n_sources >= 2 else (0.5 if n_sources == 1 else 0.0)

    value = (
        0.40 * status_component
        + 0.30 * presence_component
        + 0.20 * similarity_component
        + 0.10 * provenance_component
    )
    value = max(0.0, min(1.0, value))
    label = "high" if value >= 0.75 else "medium" if value >= 0.4 else "low"

    factors = {
        "status_component": status_component,
        "presence_component": presence_component,
        "similarity_component": round(similarity_component, 3),
        "provenance_component": provenance_component,
        "result_count": result.result_count,
        "sources": result.sources,
    }

    # Advisory-only: for a "combined" query (a well/SODIR intent that also
    # set search_text), record document evidence stats without letting
    # them influence the weighted value above - well and document
    # similarity are never averaged together.
    doc_items = [i for i in (fused.items if fused else []) if i.source_type == "document"]
    if doc_items:
        doc_sims = [i.similarity for i in doc_items if i.similarity is not None]
        factors["document_evidence_count"] = len(doc_items)
        factors["document_similarity_mean"] = round(sum(doc_sims) / len(doc_sims), 3) if doc_sims else None

    from evidence.rationale import generate_confidence_basis as _gen_basis
    basis = _gen_basis(factors, fused) if fused else []

    score = ConfidenceScore(
        value=round(value, 3),
        label=label,
        factors=factors,
        basis=basis,
    )
    meta.node_status["calculate_confidence"] = "success"
    return {"confidence": score, "execution_metadata": meta}


# ============================================================
# 6. generate_response
# ============================================================

def generate_response_node(state: GraphState) -> Dict[str, Any]:
    """Produces a deterministic, template-based answer from the resolved
    evidence. Never asks an LLM to interpret, embellish, or draw
    geological conclusions - every sentence here is built directly from
    structured fields already present in ResolutionResult.
    """

    meta = state.get("execution_metadata") or ExecutionMetadata()
    errors = state.get("errors", [])
    result = state.get("resolution_result")
    fused = state.get("fused_evidence")

    if meta.intent == "document_search":
        # document_search never produces a ResolutionResult by design
        # (see make_resolve_node) - build the answer from document
        # evidence in fused_evidence instead of the generic "result is
        # None" fallback below, which is reserved for actual failures.
        retrieve_failed = any(e.stage == "retrieve_documents" for e in errors)
        sq = state.get("structured_query")
        search_text = sq.search_text if isinstance(sq, StructuredQuery) else None

        if retrieve_failed:
            answer = "Could not complete the document search due to an internal error. See errors for detail."
        else:
            doc_items = [i for i in (fused.items if fused else []) if i.source_type == "document"]
            answer = f"Found {len(doc_items)} document chunk(s)"
            answer += f' matching "{search_text}".' if search_text else "."

        from evidence.rationale import generate_rationale as _gen_rationale_doc
        rationale = _gen_rationale_doc(meta.intent, fused) if fused else []

        meta.node_status["generate_response"] = "error" if retrieve_failed else "success"
        return {"final_answer": answer, "rationale": rationale, "execution_metadata": meta}

    if result is None:
        if errors:
            stages = ", ".join(sorted({e.stage for e in errors}))
            answer = f"Could not resolve this query ({stages} failed). See errors for detail."
        else:
            answer = "No resolution result was produced."

        from evidence.rationale import generate_rationale as _gen_rationale_err
        fused_err = state.get("fused_evidence")
        rationale = _gen_rationale_err(meta.intent, fused_err) if fused_err else []
        if not rationale:
            rationale = [f"Query could not be resolved: {stages} failed." if errors else "No resolution result was produced."]

        meta.node_status["generate_response"] = "error"
        return {"final_answer": answer, "rationale": rationale, "execution_metadata": meta}

    intent = result.intent
    n = result.result_count

    if intent == "similar_wells":
        qw = result.metadata.get("query_well", {}) or {}
        answer = f"Found {n} well(s) similar to {qw.get('well_id', 'the target well')} ({qw.get('dataset', '')})."

    elif intent == "similar_windows":
        qwin = result.metadata.get("query_window", {}) or {}
        answer = (
            f"Found {n} depth interval(s) similar to window {qwin.get('window_id')} "
            f"of {qwin.get('well_id', 'the target well')} ({qwin.get('dataset', '')})."
        )

    elif intent == "well_information":
        r = result.results or {}
        if r.get("sodir_wellbore_id"):
            answer = f"Well {r.get('well_id')} ({r.get('dataset')}) is linked to SODIR wellbore {r.get('sodir_wellbore_id')}"
            if r.get("field_name"):
                answer += f", field {r['field_name']}"
            if r.get("operator"):
                answer += f", operated by {r['operator']}"
            answer += "."
        else:
            answer = f"Well {r.get('well_id')} ({r.get('dataset')}) has no matching SODIR record."

    elif intent == "formation_information":
        answer = f"Found {n} formation top(s) for the requested well."

    elif intent == "compare_wells":
        r = result.results or {}
        t, c = r.get("target") or {}, r.get("comparison") or {}
        answer = f"Compared {t.get('well_id')} ({t.get('dataset')}) with {c.get('well_id')} ({c.get('dataset')})."
        if r.get("similarity") is not None:
            answer += f" Embedding cosine similarity: {r['similarity']:.3f}."

    elif intent == "geological_context":
        n_groups = len(result.results or [])
        answer = f"Retrieved {n} geological context record(s) across {n_groups} category group(s)."

    else:
        answer = f"Resolved intent {intent!r} with {n} result(s)."

    if result.status == "not_found":
        answer += " No SODIR-linked data was available for this well."
    elif result.status == "partial":
        answer += " Some information was unavailable."

    from evidence.rationale import generate_rationale as _gen_rationale
    fused = state.get("fused_evidence")
    rationale = _gen_rationale(intent, fused) if fused else []

    meta.node_status["generate_response"] = "success"
    return {"final_answer": answer, "rationale": rationale, "execution_metadata": meta}


# ============================================================
# 7. assess_risk
# ============================================================

def assess_risk_node(state: GraphState) -> Dict[str, Any]:
    """Runs evidence-based risk assessment using historical events
    correlated to the current well context.  Only runs when the query
    has a target well — otherwise skipped.

    All risk scores are heuristic evidence indicators, NOT calibrated
    probabilities.  No ML model is used.
    """
    from events.correlation import correlate_historical_events
    from risk.scoring import assess_all_risks
    from risk.rules import evaluate_all_rules

    meta = state.get("execution_metadata") or ExecutionMetadata()
    query = state.get("structured_query")
    errors = list(state.get("errors", []))

    if not isinstance(query, StructuredQuery) or not query.target_well_id:
        meta.node_status["assess_risk"] = "skipped"
        return {"execution_metadata": meta}

    well_id = query.target_well_id
    dataset = query.dataset_filter or "FORCE"

    try:
        correlated = correlate_historical_events(
            well_id=well_id,
            dataset=dataset,
            radius_km=50.0,
            limit=50,
        )
    except Exception as exc:
        errors.append(GraphError(
            stage="assess_risk", error_type=type(exc).__name__, message=str(exc),
        ))
        meta.node_status["assess_risk"] = "failed"
        return {"errors": errors, "execution_metadata": meta}

    well_evidence = None
    try:
        from risk.evidence_sources import gather_well_evidence
        well_evidence = gather_well_evidence(well_id, dataset)
    except Exception:
        pass

    depth_m = getattr(query, "depth_m", None)
    formation = getattr(query, "formation", None)

    risk_assessments = assess_all_risks(correlated, depth_m, formation, well_evidence)
    rule_results = evaluate_all_rules(correlated, formation)

    meta.node_status["assess_risk"] = "success"
    return {
        "risk_assessments": risk_assessments,
        "rule_results": rule_results,
        "execution_metadata": meta,
    }


# ============================================================
# 8. generate_alerts
# ============================================================

def generate_alerts_node(state: GraphState) -> Dict[str, Any]:
    """Generates evidence-backed alerts from risk assessments and
    rule results.  Recommendations are decision support only."""
    from risk.alerts import generate_all_alerts

    meta = state.get("execution_metadata") or ExecutionMetadata()
    risk_assessments = state.get("risk_assessments") or []
    rule_results = state.get("rule_results") or []

    if not risk_assessments and not rule_results:
        meta.node_status["generate_alerts"] = "skipped"
        return {"execution_metadata": meta}

    query = state.get("structured_query")
    well_id = ""
    dataset = ""
    if isinstance(query, StructuredQuery):
        well_id = query.target_well_id or ""
        dataset = query.dataset_filter or ""

    alerts = generate_all_alerts(risk_assessments, rule_results, well_id, dataset)
    meta.node_status["generate_alerts"] = "success"
    return {"alerts": alerts, "execution_metadata": meta}
