"""
Evaluation framework demo.

Runs the structured evaluation (no Groq API key needed) against the golden
query dataset, prints metrics and failures, and saves reports.

Usage:
    python examples/evaluation_demo.py
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from evaluation import (
    format_report_markdown,
    load_golden_dataset,
    run_structured_evaluation,
    save_report,
)


def main():
    print("Evaluation Framework Demo")
    print("=" * 60)

    ds = load_golden_dataset()
    print(f"Loaded {len(ds.queries)} golden queries (version {ds.version})")
    print(f"Known limitations: {len(ds.known_limitations)}")
    print()

    intents = {}
    for q in ds.queries:
        intents[q.intent] = intents.get(q.intent, 0) + 1
    print("Intent distribution:")
    for intent, count in sorted(intents.items()):
        print(f"  {intent}: {count}")
    print()

    print("Running structured evaluation (no Groq needed)...")
    report = run_structured_evaluation()

    print(f"\nResults: {report.passed}/{report.total_queries} passed "
          f"({report.pass_rate:.1%})")
    print()

    print("Metrics:")
    for m in report.metrics:
        status = "PASS" if m.value == 1.0 else "WARN"
        print(f"  [{status}] {m.name}: {m.value:.1%} ({m.passed}/{m.total})")
    print()

    if report.failed > 0:
        print(f"Failed queries ({report.failed}):")
        for r in report.results:
            if not r.passed:
                kl = " [known limitation]" if r.known_limitation else ""
                print(f"  {r.query_id}{kl}: {', '.join(r.failures)}")
        print()

    out_dir = Path("data/evaluation")
    save_report(report, out_dir / "evaluation_report.json")
    md = format_report_markdown(report)
    (out_dir / "evaluation_report.md").write_text(md)
    print(f"Reports saved to {out_dir}/")

    print()
    print("Running edge-case subset...")
    edge_report = run_structured_evaluation(tag_filter=["edge-case"])
    print(f"  Edge cases: {edge_report.passed}/{edge_report.total_queries} passed")

    print()
    print("=" * 60)
    print("Demo complete.")


if __name__ == "__main__":
    main()
