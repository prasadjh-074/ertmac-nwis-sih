"""
Demo of the deterministic retrieval library (retrieval/) against real data
in geointelligence.window_embeddings / geointelligence.well_embeddings.

Run: venv/bin/python examples/retrieval_demo.py
"""

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import retrieval as r


def print_header(title):
    print("\n" + "=" * 70)
    print(title)
    print("=" * 70)


def print_window_results(results, indent="  "):
    if not results:
        print(f"{indent}(no results)")
        return
    for res in results:
        print(
            f"{indent}#{res.rank:<2d} {res.dataset:10s} {res.well_id:28s} "
            f"win={res.window_id:<5d} depth={res.depth_start_m:8.1f}-{res.depth_end_m:8.1f}m "
            f"sim={res.similarity:6.3f} curves={res.curves_present:2d}"
        )


def print_well_results(results, indent="  "):
    if not results:
        print(f"{indent}(no results)")
        return
    for res in results:
        print(
            f"{indent}#{res.rank:<2d} {res.dataset:10s} {res.well_id:28s} "
            f"sim={res.similarity:6.3f} windows={res.windows_pooled:3d}/{res.windows_total:<3d} "
            f"pooled={res.pooling_fraction*100:5.1f}%"
        )


def pick_example_keys():
    """Grab one real FORCE window/well and one real Volve window/well to
    use as query-by-example anchors."""

    conn = r.get_connection()
    with conn.cursor() as cur:
        cur.execute(
            "SELECT dataset, well_id, window_id FROM geointelligence.window_embeddings "
            "WHERE dataset = 'FORCE_2020' AND curves_present >= 8 ORDER BY id LIMIT 1;"
        )
        force_window = cur.fetchone()

        cur.execute(
            "SELECT dataset, well_id, window_id FROM geointelligence.window_embeddings "
            "WHERE dataset = 'VOLVE' AND curves_present >= 8 ORDER BY id LIMIT 1;"
        )
        volve_window = cur.fetchone()

        cur.execute(
            "SELECT dataset, well_id FROM geointelligence.well_embeddings "
            "WHERE dataset = 'FORCE_2020' ORDER BY id LIMIT 1;"
        )
        force_well = cur.fetchone()

        cur.execute(
            "SELECT dataset, well_id FROM geointelligence.well_embeddings "
            "WHERE dataset = 'VOLVE' ORDER BY id LIMIT 1;"
        )
        volve_well = cur.fetchone()
    conn.close()
    return force_window, volve_window, force_well, volve_well


def timed(label, fn):
    start = time.perf_counter()
    result = fn()
    elapsed_ms = (time.perf_counter() - start) * 1000
    print(f"\n[{label}] query latency: {elapsed_ms:.2f} ms")
    return result, elapsed_ms


def main():
    print_header("RETRIEVAL DEMO - geointelligence.window_embeddings / .well_embeddings")

    force_window, volve_window, force_well, volve_well = pick_example_keys()
    print(f"\nAnchors:")
    print(f"  FORCE window: {force_window}")
    print(f"  Volve window: {volve_window}")
    print(f"  FORCE well:   {force_well}")
    print(f"  Volve well:   {volve_well}")

    latencies = []

    # A. Windows similar to a real FORCE window
    print_header("A. Windows similar to a real FORCE window")
    print(f"Query: {force_window}")
    results, t = timed("A", lambda: r.search_similar_windows_by_id(*force_window, top_k=5))
    latencies.append(t)
    print_window_results(results)

    # B. Windows similar to a real Volve window
    print_header("B. Windows similar to a real Volve window")
    print(f"Query: {volve_window}")
    results, t = timed("B", lambda: r.search_similar_windows_by_id(*volve_window, top_k=5))
    latencies.append(t)
    print_window_results(results)

    # C. Wells similar to a real FORCE well
    print_header("C. Wells similar to a real FORCE well")
    print(f"Query: {force_well}")
    results, t = timed("C", lambda: r.search_similar_wells_by_id(*force_well, top_k=5))
    latencies.append(t)
    print_well_results(results)

    # D. Wells similar to a real Volve well
    print_header("D. Wells similar to a real Volve well")
    print(f"Query: {volve_well}")
    results, t = timed("D", lambda: r.search_similar_wells_by_id(*volve_well, top_k=5))
    latencies.append(t)
    print_well_results(results)

    # E. Dataset filter: neighbors of a FORCE window, restricted to Volve only
    print_header("E. Dataset filter: FORCE window's neighbors, restricted to dataset=VOLVE")
    print(f"Query: {force_window}, filter dataset='VOLVE'")
    results, t = timed(
        "E",
        lambda: r.search_similar_windows_by_id(*force_window, top_k=5, dataset_filter="VOLVE"),
    )
    latencies.append(t)
    print_window_results(results)
    assert all(res.dataset == "VOLVE" for res in results), "dataset filter was not enforced"
    print("  (verified: every result has dataset='VOLVE')")

    # F. Minimum curves-present filter
    print_header("F. Minimum curves-present filter (min_curves_present=9)")
    print(f"Query: {force_window}, filter min_curves_present=9")
    results, t = timed(
        "F",
        lambda: r.search_similar_windows_by_id(*force_window, top_k=5, min_curves_present=9),
    )
    latencies.append(t)
    print_window_results(results)
    assert all(res.curves_present >= 9 for res in results), "curves_present filter was not enforced"
    print("  (verified: every result has curves_present >= 9)")

    print_header("SUMMARY")
    print(f"\nQueries run: {len(latencies)}")
    print(f"Average latency: {sum(latencies)/len(latencies):.2f} ms")
    print(f"Max latency:     {max(latencies):.2f} ms")
    print("\nAll demonstrated queries used cosine distance only, with metadata")
    print("filters pushed into SQL, and self-exclusion enforced for query-by-example.")


if __name__ == "__main__":
    main()
