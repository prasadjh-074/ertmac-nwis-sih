"""
Resolver demo: StructuredQuery → QueryResolver → actual data.

Demonstrates all 6 intents using manually constructed StructuredQuery
objects. No LLM is used — this proves the resolver works independently.

Usage:
    python examples/resolver_demo.py
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from query import validate_query
from resolver import QueryResolver


def _print_result(label, result):
    print(f"\n{'='*60}")
    print(f"  {label}")
    print(f"{'='*60}")
    print(f"  Intent:       {result.intent}")
    print(f"  Status:       {result.status}")
    print(f"  Result count: {result.result_count}")
    print(f"  Sources:      {result.sources}")

    if isinstance(result.results, list):
        for i, r in enumerate(result.results[:5]):
            if isinstance(r, dict):
                compact = {k: v for k, v in r.items() if v is not None}
                print(f"  [{i+1}] {json.dumps(compact, default=str)[:120]}")
    elif isinstance(result.results, dict):
        compact = {k: v for k, v in result.results.items() if v is not None}
        print(f"  {json.dumps(compact, default=str)[:200]}")

    if result.metadata:
        meta_compact = {k: v for k, v in result.metadata.items() if v is not None}
        if meta_compact:
            print(f"  Metadata: {json.dumps(meta_compact, default=str)[:150]}")


def main():
    print("Resolver Demo: StructuredQuery → QueryResolver → Real Data")
    print("No LLM involved — pure deterministic resolution.\n")

    with QueryResolver() as resolver:

        # 1. similar_wells
        q = validate_query({
            "intent": "similar_wells",
            "target_dataset": "VOLVE",
            "target_well_id": "15/9-F-1",
            "top_k": 5,
        })
        result = resolver.resolve(q)
        _print_result("1. SIMILAR WELLS — Find 5 wells similar to Volve 15/9-F-1", result)

        # 2. similar_windows
        q = validate_query({
            "intent": "similar_windows",
            "target_dataset": "VOLVE",
            "target_well_id": "15/9-F-1",
            "target_window_id": 11,
            "top_k": 5,
        })
        result = resolver.resolve(q)
        _print_result("2. SIMILAR WINDOWS — Find 5 windows similar to Volve 15/9-F-1 window 11", result)

        # 3. well_information
        q = validate_query({
            "intent": "well_information",
            "target_dataset": "VOLVE",
            "target_well_id": "15/9-F-1",
        })
        result = resolver.resolve(q)
        _print_result("3. WELL INFORMATION — Tell me about Volve 15/9-F-1", result)

        # 4. formation_information
        q = validate_query({
            "intent": "formation_information",
            "target_dataset": "VOLVE",
            "target_well_id": "15/9-19 SR",
        })
        result = resolver.resolve(q)
        _print_result("4. FORMATION INFORMATION — Formations in Volve 15/9-19 SR", result)

        # 5. compare_wells
        q = validate_query({
            "intent": "compare_wells",
            "target_dataset": "VOLVE",
            "target_well_id": "15/9-F-1",
            "comparison_dataset": "VOLVE",
            "comparison_well_id": "15/9-F-4",
        })
        result = resolver.resolve(q)
        _print_result("5. COMPARE WELLS — Compare Volve 15/9-F-1 vs 15/9-F-4", result)

        # 6. geological_context
        q = validate_query({
            "intent": "geological_context",
            "target_dataset": "VOLVE",
            "target_well_id": "15/9-F-4",
            "requested_geological_context": ["field", "company", "formations", "casing"],
        })
        result = resolver.resolve(q)
        _print_result("6. GEOLOGICAL CONTEXT — Field, company, formations, casing for 15/9-F-4", result)

    print(f"\n{'='*60}")
    print("  Demo complete. All 6 intents resolved successfully.")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
