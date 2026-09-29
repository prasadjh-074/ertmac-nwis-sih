"""CLI entrypoint: `python -m ingestion.pipeline --input <path>`."""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from ingestion.config import get_settings
from ingestion.pipeline.run import run_pipeline
from ingestion.schemas import IngestionSummary

_TYPE_LABELS = {
    "WELL": "Wells", "WELLBORE": "Wellbores", "FIELD": "Fields",
    "DISCOVERY": "Discoveries", "LICENCE": "Licences", "COMPANY": "Companies",
    "FORMATION": "Formations", "LITHOLOGY": "Lithologies", "RESERVOIR": "Reservoirs",
    "DEPTH": "Depths", "DEPTH_INTERVAL": "Depth Intervals", "DATE": "Dates",
    "LOG_CURVE": "Log Curves", "PRODUCTION": "Production Records",
    "PRESSURE": "Pressures", "DRILLING_EVENT": "Drilling Events",
    "COMPLETION": "Completions",
}


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m ingestion.pipeline")
    parser.add_argument("--input", required=True, help="Path to a document file or a directory of documents")
    parser.add_argument("--source", default=None, help="Override source type detection: pdf|text|image")
    parser.add_argument("--verbose", action="store_true")
    return parser


def _iter_input_files(input_path: str) -> list[str]:
    path = Path(input_path)
    if path.is_dir():
        return sorted(str(p) for p in path.iterdir() if p.is_file())
    return [str(path)]


def _merge_summaries(summaries: list[IngestionSummary]) -> IngestionSummary:
    if len(summaries) == 1:
        return summaries[0]

    merged = IngestionSummary(
        run_id=",".join(s.run_id for s in summaries),
        source_path=summaries[0].source_path if summaries else "",
        status="SUCCESS",
    )
    for s in summaries:
        merged.documents_processed += s.documents_processed
        merged.pages_processed += s.pages_processed
        merged.entities_extracted += s.entities_extracted
        merged.entities_resolved += s.entities_resolved
        merged.entities_unresolved += s.entities_unresolved
        merged.relations_extracted += s.relations_extracted
        merged.chunks_created += s.chunks_created
        merged.embeddings_created += s.embeddings_created
        merged.warnings.extend(s.warnings)
        merged.errors.extend(s.errors)
        merged.duration_seconds += s.duration_seconds
        for k, v in s.entities_by_type.items():
            merged.entities_by_type[k] = merged.entities_by_type.get(k, 0) + v
        if s.status == "FAILED":
            merged.status = "FAILED"
        elif s.status == "SUCCESS_WITH_WARNINGS" and merged.status != "FAILED":
            merged.status = "SUCCESS_WITH_WARNINGS"
    return merged


def print_summary(summary: IngestionSummary) -> None:
    bar = "=" * 50
    print(f"\n{bar}\nINGESTION COMPLETE\n{bar}\n")
    print(f"Status: {summary.status}")
    print(f"Documents: {summary.documents_processed}")
    print(f"Pages: {summary.pages_processed}\n")

    print("Entities:")
    if summary.entities_by_type:
        for entity_type, count in sorted(summary.entities_by_type.items()):
            label = _TYPE_LABELS.get(entity_type, entity_type.title() + "s")
            print(f"    {label}: {count}")
    else:
        print("    (none extracted)")
    print()

    print(f"Relations: {summary.relations_extracted}\n")
    print(f"Resolved: {summary.entities_resolved}")
    print(f"Unresolved: {summary.entities_unresolved}\n")
    print(f"Chunks: {summary.chunks_created}")
    print(f"Embeddings: {summary.embeddings_created}\n")

    print(f"Warnings: {len(summary.warnings)}")
    for w in summary.warnings:
        print(f"    - {w}")
    print(f"Errors: {len(summary.errors)}")
    for e in summary.errors:
        print(f"    - {e}")

    print(f"\nDuration: {summary.duration_seconds:.2f}s")
    print(f"\n{bar}\n")


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    settings = get_settings()
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else getattr(logging, settings.log_level, logging.INFO),
        format="%(levelname)s %(name)s: %(message)s",
    )

    files = _iter_input_files(args.input)
    summaries = [run_pipeline(f, source_override=args.source) for f in files]
    summary = _merge_summaries(summaries)
    print_summary(summary)
    return 1 if summary.status == "FAILED" else 0


if __name__ == "__main__":
    sys.exit(main())
