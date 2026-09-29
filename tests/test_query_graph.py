"""
Tests for the query-time LangGraph orchestration (graph/).

Unit tests mock GroqInterpreter and QueryResolver - no live Groq API key
or live database is required. An integration test at the bottom exercises
the real local retrieval/SODIR data with only the Groq boundary mocked.
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from graph import ConfidenceScore, EvidenceItem, QueryGraphRunner, QueryResponse
from llm.groq_interpreter import InterpretationError, InterpretationResult
from query import StructuredQuery, validate_query
from resolver.errors import EntityNotFoundError
from resolver.models import ResolutionResult


# ============================================================
# Helpers
# ============================================================

def _make_resolution_result(**overrides) -> ResolutionResult:
    defaults = dict(
        intent="similar_wells",
        status="success",
        query={"intent": "similar_wells", "target_dataset": "VOLVE", "target_well_id": "15/9-F-1", "top_k": 5},
        results=[
            {"dataset": "VOLVE", "well_id": "15/9-F-4", "similarity": 0.92, "rank": 1,
             "windows_total": 100, "windows_pooled": 90, "windows_excluded": 10, "pooling_fraction": 0.9},
            {"dataset": "FORCE_2020", "well_id": "34/6-1", "similarity": 0.85, "rank": 2,
             "windows_total": 200, "windows_pooled": 180, "windows_excluded": 20, "pooling_fraction": 0.9},
        ],
        result_count=2,
        sources=["VOLVE", "FORCE_2020"],
        metadata={"query_well": {"dataset": "VOLVE", "well_id": "15/9-F-1"}},
    )
    defaults.update(overrides)
    return ResolutionResult(**defaults)


def _make_mock_resolver(resolution_result=None, raise_error=None):
    mock_resolver = MagicMock()
    if raise_error is not None:
        mock_resolver.resolve.side_effect = raise_error
    else:
        mock_resolver.resolve.return_value = resolution_result or _make_resolution_result()
    mock_resolver.close = MagicMock()
    return mock_resolver


def _make_mock_interpreter(structured_query_dict=None, raise_error=None):
    mock_interp = MagicMock()
    if raise_error is not None:
        mock_interp.interpret.side_effect = raise_error
    else:
        q = validate_query(structured_query_dict or {
            "intent": "similar_wells", "target_dataset": "VOLVE",
            "target_well_id": "15/9-F-1", "top_k": 5,
        })
        mock_interp.interpret.return_value = InterpretationResult(
            query=q, model="mock-model", latency_ms=10.0,
            prompt_tokens=100, completion_tokens=20, raw_json={}, retries=0,
        )
    return mock_interp


def _make_runner(resolution_result=None, resolver_error=None, interpreter=None):
    resolver_factory = lambda: _make_mock_resolver(resolution_result, resolver_error)
    return QueryGraphRunner(interpreter=interpreter, resolver_factory=resolver_factory, use_llm=interpreter is not None)


# ============================================================
# 1. similar_wells (via natural language + mocked Groq)
# ============================================================

def test_similar_wells_via_mocked_groq():
    interp = _make_mock_interpreter({
        "intent": "similar_wells", "target_dataset": "VOLVE", "target_well_id": "15/9-F-1", "top_k": 5,
    })
    resolver_factory = lambda: _make_mock_resolver(_make_resolution_result())
    runner = QueryGraphRunner(interpreter=interp, resolver_factory=resolver_factory, use_llm=True)

    resp = runner.run_query("Find wells similar to 15/9-F-1")

    assert isinstance(resp, QueryResponse)
    assert resp.structured_query["intent"] == "similar_wells"
    assert resp.metadata.llm_used is True
    assert resp.metadata.intent == "similar_wells"
    assert "Found 2 well(s)" in resp.answer
    assert len(resp.evidence) == 2
    assert resp.evidence[0].source_system == "VOLVE"
    assert resp.errors == []


# ============================================================
# 2. similar_windows (deterministic mode)
# ============================================================

def test_similar_windows_deterministic():
    result = _make_resolution_result(
        intent="similar_windows",
        results=[
            {"dataset": "FORCE_2020", "well_id": "34/6-1", "window_id": 10,
             "depth_start_m": 1000.0, "depth_end_m": 1020.0, "similarity": 0.88, "rank": 1, "curves_present": 8},
        ],
        result_count=1,
        sources=["FORCE_2020"],
        metadata={"query_window": {"dataset": "VOLVE", "well_id": "15/9-F-1", "window_id": 11}},
    )
    runner = _make_runner(resolution_result=result)

    resp = runner.run_structured_query({
        "intent": "similar_windows", "target_dataset": "VOLVE",
        "target_well_id": "15/9-F-1", "target_window_id": 11, "top_k": 5,
    })

    assert "Found 1 depth interval(s)" in resp.answer
    assert resp.evidence[0].entity_type == "window"
    assert resp.evidence[0].source_id == "10"
    assert resp.metadata.llm_used is False


# ============================================================
# 3. well_information
# ============================================================

def test_well_information_deterministic():
    result = _make_resolution_result(
        intent="well_information",
        status="success",
        results={
            "dataset": "VOLVE", "well_id": "15/9-F-1", "source_system": "SODIR",
            "sodir_wellbore_id": 6419, "field_name": "VOLVE", "operator": "Equinor",
        },
        result_count=1,
        sources=["VOLVE", "SODIR"],
        metadata={"sodir_linked": True},
    )
    runner = _make_runner(resolution_result=result)

    resp = runner.run_structured_query({
        "intent": "well_information", "target_dataset": "VOLVE", "target_well_id": "15/9-F-1",
    })

    assert "linked to SODIR wellbore 6419" in resp.answer
    assert "VOLVE" in resp.answer
    assert resp.evidence[0].entity_type == "well_info"
    assert resp.evidence[0].source_id == "6419"
    assert "SODIR" in resp.provenance


# ============================================================
# 4. formation_information
# ============================================================

def test_formation_information_deterministic():
    result = _make_resolution_result(
        intent="formation_information",
        status="success",
        query={"intent": "formation_information", "target_dataset": "VOLVE", "target_well_id": "15/9-19 SR"},
        results=[
            {"source_system": "SODIR", "formation_name": "UTSIRA FM", "formation_id": 80,
             "top_depth_m": 846.0, "base_depth_m": 1080.0, "parent_formation_name": None, "stratigraphic_age": None},
        ],
        result_count=1,
        sources=["VOLVE", "SODIR"],
        metadata={"wellbore_id": 1990},
    )
    runner = _make_runner(resolution_result=result)

    resp = runner.run_structured_query({
        "intent": "formation_information", "target_dataset": "VOLVE", "target_well_id": "15/9-19 SR",
    })

    assert "Found 1 formation top(s)" in resp.answer
    assert resp.evidence[0].entity_type == "formation"
    assert resp.evidence[0].well_id == "15/9-19 SR"
    assert resp.evidence[0].source_id == "80"


# ============================================================
# 5. compare_wells
# ============================================================

def test_compare_wells_deterministic():
    result = _make_resolution_result(
        intent="compare_wells",
        status="success",
        query={"intent": "compare_wells", "target_dataset": "VOLVE", "target_well_id": "15/9-F-1",
               "comparison_dataset": "VOLVE", "comparison_well_id": "15/9-F-4"},
        results={
            "target": {"dataset": "VOLVE", "well_id": "15/9-F-1", "source_system": "SODIR", "sodir_wellbore_id": 100},
            "comparison": {"dataset": "VOLVE", "well_id": "15/9-F-4", "source_system": "SODIR", "sodir_wellbore_id": 200},
            "similarity": 0.87,
        },
        result_count=2,
        sources=["VOLVE", "SODIR"],
        metadata={},
    )
    runner = _make_runner(resolution_result=result)

    resp = runner.run_structured_query({
        "intent": "compare_wells", "target_dataset": "VOLVE", "target_well_id": "15/9-F-1",
        "comparison_dataset": "VOLVE", "comparison_well_id": "15/9-F-4",
    })

    assert "Compared 15/9-F-1" in resp.answer
    assert "0.870" in resp.answer
    assert len(resp.evidence) == 3  # target, comparison, similarity_score
    entity_types = [e.entity_type for e in resp.evidence]
    assert "similarity_score" in entity_types


# ============================================================
# 6. geological_context
# ============================================================

def test_geological_context_deterministic():
    result = _make_resolution_result(
        intent="geological_context",
        status="success",
        query={"intent": "geological_context", "target_dataset": "VOLVE", "target_well_id": "15/9-F-4",
               "requested_geological_context": ["field", "company"]},
        results=[
            {"entity_type": "field", "source_system": "SODIR",
             "records": [{"field_id": 1, "field_name": "VOLVE"}], "record_count": 1},
            {"entity_type": "company", "source_system": "SODIR",
             "records": [{"company_name": "Equinor", "role": "OPERATOR"}], "record_count": 1},
        ],
        result_count=2,
        sources=["VOLVE", "SODIR"],
        metadata={"wellbore_id": 12345},
    )
    runner = _make_runner(resolution_result=result)

    resp = runner.run_structured_query({
        "intent": "geological_context", "target_dataset": "VOLVE", "target_well_id": "15/9-F-4",
        "requested_geological_context": ["field", "company"],
    })

    assert "Retrieved 2 geological context record(s) across 2 category group(s)" in resp.answer
    assert len(resp.evidence) == 2
    assert {e.entity_type for e in resp.evidence} == {"field", "company"}
    assert all(e.well_id == "15/9-F-4" for e in resp.evidence)


# ============================================================
# 7. invalid query
# ============================================================

def test_invalid_query_stops_before_resolve():
    resolver = MagicMock()
    runner = QueryGraphRunner(resolver_factory=lambda: resolver, use_llm=False)

    resp = runner.run_structured_query({"intent": "similar_wells"})  # missing required fields

    assert resp.errors[0].stage == "validate"
    assert "requires field" in resp.errors[0].message
    resolver.resolve.assert_not_called()
    assert resp.confidence_score.value == 0.0
    assert resp.confidence_score.label == "none"
    assert resp.evidence == []


def test_invalid_enum_value_rejected():
    resolver = MagicMock()
    runner = QueryGraphRunner(resolver_factory=lambda: resolver, use_llm=False)

    resp = runner.run_structured_query({
        "intent": "similar_wells", "target_dataset": "NOT_REAL", "target_well_id": "15/9-F-1",
    })

    assert len(resp.errors) == 1
    assert resp.errors[0].stage == "validate"
    resolver.resolve.assert_not_called()


# ============================================================
# 8. resolver failure
# ============================================================

def test_resolver_failure_handled_cleanly():
    runner = _make_runner(resolver_error=EntityNotFoundError("well", "NONEXISTENT", "VOLVE"))

    resp = runner.run_structured_query({
        "intent": "similar_wells", "target_dataset": "VOLVE", "target_well_id": "NONEXISTENT",
    })

    assert resp.errors[0].stage == "resolve"
    assert resp.errors[0].error_type == "EntityNotFoundError"
    assert "Could not resolve" in resp.answer
    assert resp.confidence_score.value == 0.0


def test_groq_interpretation_failure_handled_cleanly():
    interp = _make_mock_interpreter(raise_error=InterpretationError("Groq API call failed: timeout"))
    resolver_factory = lambda: _make_mock_resolver()
    runner = QueryGraphRunner(interpreter=interp, resolver_factory=resolver_factory, use_llm=True)

    resp = runner.run_query("some question")

    assert resp.errors[0].stage == "interpret"
    assert resp.errors[0].error_type == "InterpretationError"
    assert resp.metadata.llm_used is True
    assert resp.confidence_score.value == 0.0
    assert resp.confidence_score.label == "none"


# ============================================================
# 9. no-result query
# ============================================================

def test_no_result_query():
    result = _make_resolution_result(results=[], result_count=0, sources=["VOLVE"])
    runner = _make_runner(resolution_result=result)

    resp = runner.run_structured_query({
        "intent": "similar_wells", "target_dataset": "VOLVE", "target_well_id": "15/9-F-1",
    })

    assert resp.evidence == []
    assert "Found 0 well(s)" in resp.answer
    assert resp.confidence_score.factors["presence_component"] == 0.0
    # status=success(0.4) + presence=0 + similarity=0 + provenance=1 source(0.05) = 0.45 -> "medium"
    assert resp.confidence_score.label == "medium"


# ============================================================
# 10. provenance preservation
# ============================================================

def test_provenance_preserved_across_datasets():
    result = _make_resolution_result(
        results=[
            {"dataset": "VOLVE", "well_id": "15/9-F-4", "similarity": 0.9, "rank": 1,
             "windows_total": 1, "windows_pooled": 1, "windows_excluded": 0, "pooling_fraction": 1.0},
            {"dataset": "FORCE_2020", "well_id": "34/6-1", "similarity": 0.8, "rank": 2,
             "windows_total": 1, "windows_pooled": 1, "windows_excluded": 0, "pooling_fraction": 1.0},
        ],
        sources=["VOLVE", "FORCE_2020"],
    )
    runner = _make_runner(resolution_result=result)

    resp = runner.run_structured_query({
        "intent": "similar_wells", "target_dataset": "VOLVE", "target_well_id": "15/9-F-1",
    })

    assert sorted(resp.provenance) == ["FORCE_2020", "VOLVE"]
    assert resp.evidence[0].source_system == "VOLVE"
    assert resp.evidence[1].source_system == "FORCE_2020"
    # FORCE, Volve, SODIR are never collapsed into one indistinguishable label
    assert len({e.source_system for e in resp.evidence}) == 2


def test_geological_context_preserves_sodir_provenance():
    result = _make_resolution_result(
        intent="geological_context", status="success",
        query={"intent": "geological_context", "target_dataset": "VOLVE", "target_well_id": "15/9-F-1"},
        results=[{"entity_type": "field", "source_system": "SODIR",
                  "records": [{"field_name": "VOLVE"}], "record_count": 1}],
        result_count=1, sources=["VOLVE", "SODIR"], metadata={},
    )
    runner = _make_runner(resolution_result=result)

    resp = runner.run_structured_query({
        "intent": "geological_context", "target_dataset": "VOLVE", "target_well_id": "15/9-F-1",
    })

    assert resp.evidence[0].source_system == "SODIR"
    assert "SODIR" in resp.provenance


# ============================================================
# 11. confidence calculation
# ============================================================

def test_confidence_high_for_successful_similarity_query():
    result = _make_resolution_result(
        results=[
            {"dataset": "VOLVE", "well_id": "a", "similarity": 0.95, "rank": 1,
             "windows_total": 1, "windows_pooled": 1, "windows_excluded": 0, "pooling_fraction": 1.0},
        ],
        result_count=1, sources=["VOLVE", "FORCE_2020"],
    )
    runner = _make_runner(resolution_result=result)
    resp = runner.run_structured_query({
        "intent": "similar_wells", "target_dataset": "VOLVE", "target_well_id": "15/9-F-1",
    })

    assert resp.confidence_score.label == "high"
    assert resp.confidence_score.value > 0.75
    assert "not a calibrated probability" in resp.confidence_score.note


def test_confidence_zero_for_not_found_status():
    result = _make_resolution_result(
        intent="formation_information", status="not_found",
        results=[], result_count=0, sources=["VOLVE"],
    )
    runner = _make_runner(resolution_result=result)
    resp = runner.run_structured_query({
        "intent": "formation_information", "target_dataset": "VOLVE", "target_well_id": "UNKNOWN",
    })

    assert resp.confidence_score.factors["status_component"] == 0.0
    assert resp.confidence_score.label == "low"


def test_confidence_neutral_similarity_for_non_similarity_intent():
    result = _make_resolution_result(
        intent="well_information", status="success",
        results={"dataset": "VOLVE", "well_id": "15/9-F-1", "source_system": "SODIR", "sodir_wellbore_id": 1},
        result_count=1, sources=["VOLVE", "SODIR"],
    )
    runner = _make_runner(resolution_result=result)
    resp = runner.run_structured_query({
        "intent": "well_information", "target_dataset": "VOLVE", "target_well_id": "15/9-F-1",
    })

    assert resp.confidence_score.factors["similarity_component"] == 0.5


# ============================================================
# 12. final response generation
# ============================================================

def test_final_answer_never_contains_geological_interpretation():
    """Guard against future regressions that might route the answer
    through an LLM - the current implementation is template-only."""
    result = _make_resolution_result()
    runner = _make_runner(resolution_result=result)
    resp = runner.run_structured_query({
        "intent": "similar_wells", "target_dataset": "VOLVE", "target_well_id": "15/9-F-1",
    })

    forbidden_terms = ["probably", "likely indicates", "suggests that the reservoir", "I think", "in my opinion"]
    for term in forbidden_terms:
        assert term not in resp.answer.lower()


def test_response_is_query_response_instance():
    result = _make_resolution_result()
    runner = _make_runner(resolution_result=result)
    resp = runner.run_structured_query({
        "intent": "similar_wells", "target_dataset": "VOLVE", "target_well_id": "15/9-F-1",
    })
    assert isinstance(resp, QueryResponse)
    assert isinstance(resp.evidence[0], EvidenceItem)
    assert isinstance(resp.confidence_score, ConfidenceScore)
    assert resp.metadata.total_execution_ms is not None
    assert resp.metadata.total_execution_ms >= 0


# ============================================================
# Integration test: real local retrieval/SODIR data, Groq mocked
# ============================================================

def _db_available():
    try:
        from retrieval.vector_search import get_connection
        conn = get_connection()
        conn.close()
        return True
    except Exception:
        return False


@pytest.mark.integration
@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_integration_nl_question_through_real_resolver():
    """Groq boundary is mocked (no live API key required); everything
    downstream - QueryResolver, retrieval, SODIR - is real."""
    interp = _make_mock_interpreter({
        "intent": "similar_wells", "target_dataset": "VOLVE", "target_well_id": "15/9-F-1", "top_k": 3,
    })
    runner = QueryGraphRunner(interpreter=interp, use_llm=True)

    resp = runner.run_query("What wells are similar to 15/9-F-1?")

    assert resp.metadata.llm_used is True
    assert resp.metadata.intent == "similar_wells"
    assert len(resp.evidence) > 0
    assert len(resp.evidence) <= 3
    for e in resp.evidence:
        assert e.well_id != "15/9-F-1"  # query well excluded from its own results
    assert resp.confidence_score is not None
    assert "Found" in resp.answer


# ============================================================
# 13. document_search (document-only, no ResolutionResult)
# ============================================================

def test_document_search_skips_resolver():
    """document_search never touches the well/SODIR resolver - resolve
    should be skipped cleanly, not treated as a failure."""
    resolver = MagicMock()
    runner = QueryGraphRunner(resolver_factory=lambda: resolver, use_llm=False)

    with patch("document_retrieval.search.search_documents", return_value=[]):
        resp = runner.run_structured_query({
            "intent": "document_search", "search_text": "formation tops", "top_k": 5,
        })

    resolver.resolve.assert_not_called()
    assert resp.errors == []
    assert resp.metadata.node_status.get("resolve") == "skipped_document_only"


def test_document_search_builds_evidence_from_results():
    from document_retrieval.models import DocumentSearchResult

    fake_results = [
        DocumentSearchResult(
            chunk_id="c1", document_id="d1", file_name="report.pdf",
            page_number=2, chunk_index=0, section="FORMATION TOPS",
            text="Heimdal 2450m", similarity=0.82, rank=1,
        ),
    ]
    resolver = MagicMock()
    runner = QueryGraphRunner(resolver_factory=lambda: resolver, use_llm=False)

    with patch("document_retrieval.search.search_documents", return_value=fake_results):
        resp = runner.run_structured_query({
            "intent": "document_search", "search_text": "formation tops", "top_k": 5,
        })

    assert len(resp.evidence) == 1
    ev = resp.evidence[0]
    assert ev.source_system == "DOCUMENT"
    assert ev.entity_type == "document_chunk"
    assert ev.source_id == "c1"
    assert ev.similarity == 0.82
    assert ev.metadata["file_name"] == "report.pdf"
    assert "Found 1 document chunk(s)" in resp.answer
    assert resp.metadata.document_result_count == 1


def test_document_search_zero_results():
    resolver = MagicMock()
    runner = QueryGraphRunner(resolver_factory=lambda: resolver, use_llm=False)

    with patch("document_retrieval.search.search_documents", return_value=[]):
        resp = runner.run_structured_query({
            "intent": "document_search", "search_text": "nonexistent topic", "top_k": 5,
        })

    assert resp.evidence == []
    assert "Found 0 document chunk(s)" in resp.answer
    assert resp.confidence_score.label in ("low", "medium", "none")


def test_document_search_retrieval_failure_handled_cleanly():
    resolver = MagicMock()
    runner = QueryGraphRunner(resolver_factory=lambda: resolver, use_llm=False)

    with patch("document_retrieval.search.search_documents", side_effect=RuntimeError("db down")):
        resp = runner.run_structured_query({
            "intent": "document_search", "search_text": "formation tops", "top_k": 5,
        })

    assert len(resp.errors) == 1
    assert resp.errors[0].stage == "retrieve_documents"
    assert resp.confidence_score.value == 0.0
    assert resp.confidence_score.label == "none"
    assert "Could not complete the document search" in resp.answer


def test_document_search_missing_search_text_invalid():
    resolver = MagicMock()
    runner = QueryGraphRunner(resolver_factory=lambda: resolver, use_llm=False)

    resp = runner.run_structured_query({"intent": "document_search"})

    assert resp.errors[0].stage == "validate"
    resolver.resolve.assert_not_called()


# ============================================================
# 14. combined queries (well/SODIR intent + search_text)
# ============================================================

def test_combined_query_merges_well_and_document_evidence():
    from document_retrieval.models import DocumentSearchResult

    fake_doc_results = [
        DocumentSearchResult(
            chunk_id="c1", document_id="d1", file_name="report.pdf",
            page_number=1, chunk_index=0, section=None,
            text="Well 15/9-F-1 info", similarity=0.7, rank=1,
        ),
    ]
    result = _make_resolution_result(
        intent="well_information", status="success",
        results={"dataset": "VOLVE", "well_id": "15/9-F-1", "source_system": "SODIR",
                  "sodir_wellbore_id": 6419},
        result_count=1, sources=["VOLVE", "SODIR"],
    )
    runner = _make_runner(resolution_result=result)

    with patch("document_retrieval.search.search_documents", return_value=fake_doc_results):
        resp = runner.run_structured_query({
            "intent": "well_information", "target_dataset": "VOLVE",
            "target_well_id": "15/9-F-1", "search_text": "well info",
        })

    entity_types = {e.entity_type for e in resp.evidence}
    assert "well_info" in entity_types
    assert "document_chunk" in entity_types
    assert "DOCUMENT" in resp.provenance
    assert "SODIR" in resp.provenance
    # Well confidence formula stays unaffected by document evidence -
    # document stats are advisory-only.
    assert resp.confidence_score.factors["document_evidence_count"] == 1
    assert "similarity_component" in resp.confidence_score.factors


def test_combined_query_without_search_text_unaffected():
    """A plain well_information query (no search_text) must never touch
    document retrieval - retrieve_documents should be a clean skip."""
    result = _make_resolution_result(
        intent="well_information", status="success",
        results={"dataset": "VOLVE", "well_id": "15/9-F-1", "source_system": "SODIR",
                  "sodir_wellbore_id": 6419},
        result_count=1, sources=["VOLVE", "SODIR"],
    )
    runner = _make_runner(resolution_result=result)

    resp = runner.run_structured_query({
        "intent": "well_information", "target_dataset": "VOLVE", "target_well_id": "15/9-F-1",
    })

    assert resp.metadata.node_status.get("retrieve_documents") == "skipped"
    assert "document_evidence_count" not in resp.confidence_score.factors
    assert all(e.entity_type != "document_chunk" for e in resp.evidence)


@pytest.mark.integration
@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_integration_formation_information_real_data():
    interp = _make_mock_interpreter({
        "intent": "formation_information", "target_dataset": "VOLVE", "target_well_id": "15/9-19 SR",
    })
    runner = QueryGraphRunner(interpreter=interp, use_llm=True)

    resp = runner.run_query("What formations are present in 15/9-19 SR?")

    assert resp.metadata.intent == "formation_information"
    assert resp.metadata.result_count is not None and resp.metadata.result_count > 0
    assert all(e.source_system == "SODIR" for e in resp.evidence)
