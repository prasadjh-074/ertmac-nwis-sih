"""
Query graph demo: natural language -> LangGraph orchestration -> QueryResponse.

Demonstrates the full pipeline:
    user question -> GroqInterpreter -> StructuredQuery -> QueryResolver
    -> evidence -> confidence -> deterministic answer

Uses the real Groq interpreter if GROQ_API_KEY is configured; otherwise
falls back to a deterministic StructuredQuery mode (run_structured_query)
that bypasses Groq entirely but exercises the same downstream graph.

Usage:
    python examples/query_graph_demo.py
"""

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv

load_dotenv()

from graph import QueryGraphRunner


def _print_response(label, resp):
    print(f"\n{'='*70}")
    print(f"  {label}")
    print(f"{'='*70}")

    print(f"\n  ANSWER")
    print(f"  {resp.answer}")

    print(f"\n  WHY (rationale)")
    if resp.rationale:
        for i, r in enumerate(resp.rationale, 1):
            print(f"  {i}. {r}")
    else:
        print(f"  (none)")

    print(f"\n  EVIDENCE ({len(resp.evidence)} item(s))")
    for i, e in enumerate(resp.evidence[:5], 1):
        sim = f", similarity={e.similarity:.3f}" if e.similarity else ""
        print(f"  {i}. [{e.source_system}/{e.entity_type}] well_id={e.well_id}{sim}")

    print(f"\n  PROVENANCE")
    print(f"  {resp.provenance}")

    print(f"\n  CONFIDENCE")
    print(f"  {resp.confidence_score.value} — {resp.confidence_score.label}")
    print(f"  is_probability: {resp.confidence_score.is_probability}")

    print(f"\n  CONFIDENCE BASIS")
    if resp.confidence_score.basis:
        for b in resp.confidence_score.basis:
            print(f"  - {b}")

    print(f"\n  Execution: {resp.metadata.total_execution_ms:.1f}ms, "
          f"llm_used={resp.metadata.llm_used}")
    if resp.errors:
        print(f"  Errors: {resp.errors}")


def main():
    has_groq_key = bool(os.getenv("GROQ_API_KEY"))

    print("LangGraph Query Orchestration Demo")
    print(f"Groq API key configured: {has_groq_key}")

    if has_groq_key:
        print("Using the REAL Groq interpreter for natural-language questions.\n")
        runner = QueryGraphRunner(use_llm=True)

        resp1 = runner.run_query("What wells are similar to 15/9-F-1?")
        _print_response('1. NL: "What wells are similar to 15/9-F-1?"', resp1)

        resp2 = runner.run_query("What formations are present in 15/9-19 SR?")
        _print_response('2. NL: "What formations are present in 15/9-19 SR?"', resp2)

    else:
        print("No GROQ_API_KEY found - using deterministic StructuredQuery mode ")
        print("(bypasses Groq, exercises the same validate->resolve->evidence->")
        print("confidence->response graph).\n")
        runner = QueryGraphRunner(use_llm=False)

        resp1 = runner.run_structured_query({
            "intent": "similar_wells",
            "target_dataset": "VOLVE",
            "target_well_id": "15/9-F-1",
            "top_k": 5,
        })
        _print_response('1. Deterministic: similar_wells for 15/9-F-1', resp1)

        resp2 = runner.run_structured_query({
            "intent": "formation_information",
            "target_dataset": "VOLVE",
            "target_well_id": "15/9-19 SR",
        })
        _print_response('2. Deterministic: formation_information for 15/9-19 SR', resp2)

    # A few more intents regardless of mode, always deterministic to keep the demo self-contained.
    runner2 = QueryGraphRunner(use_llm=False)

    resp3 = runner2.run_structured_query({
        "intent": "well_information",
        "target_dataset": "VOLVE",
        "target_well_id": "15/9-F-1",
    })
    _print_response("3. well_information for 15/9-F-1", resp3)

    resp4 = runner2.run_structured_query({
        "intent": "compare_wells",
        "target_dataset": "VOLVE",
        "target_well_id": "15/9-F-1",
        "comparison_dataset": "VOLVE",
        "comparison_well_id": "15/9-F-4",
    })
    _print_response("4. compare_wells: 15/9-F-1 vs 15/9-F-4", resp4)

    resp5 = runner2.run_structured_query({
        "intent": "geological_context",
        "target_dataset": "VOLVE",
        "target_well_id": "15/9-F-1",
        "requested_geological_context": ["field", "company"],
    })
    _print_response("5. geological_context for 15/9-F-1", resp5)

    resp6 = runner2.run_structured_query({
        "intent": "well_information",
        "target_dataset": "FORCE_2020",
        "target_well_id": "34/6-1",
    })
    _print_response("6. well_information for 34/6-1 (no SODIR link — missing info demo)", resp6)

    resp7 = runner2.run_structured_query({"intent": "similar_wells"})  # invalid on purpose
    _print_response("7. Invalid query (missing required fields)", resp7)

    # Document retrieval (384-dim sentence-transformer space, completely
    # separate from the 30-dim well/window embeddings above) - see
    # docs/document_retrieval.md.
    resp8 = runner2.run_structured_query({
        "intent": "document_search",
        "search_text": "What formation tops are present in well 30/6-1?",
        "top_k": 5,
    })
    _print_response("8. document_search: formation tops in well 30/6-1", resp8)

    resp9 = runner2.run_structured_query({
        "intent": "well_information",
        "target_dataset": "VOLVE",
        "target_well_id": "15/9-F-1",
        "search_text": "well report information",
    })
    _print_response("9. Combined: well_information + document search_text", resp9)

    print(f"\n{'='*70}")
    print("  Demo complete.")
    print(f"{'='*70}")


if __name__ == "__main__":
    main()
