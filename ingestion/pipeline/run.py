"""Top-level orchestration entrypoint: builds the LangGraph workflow, runs
it end-to-end for a single document, and assembles an IngestionSummary.
"""
from __future__ import annotations

import time
import uuid
from collections import Counter

from ingestion.config import get_settings
from ingestion.graph.state import PipelineState
from ingestion.graph.workflow import build_graph
from ingestion.schemas import IngestionSummary
from ingestion.storage.db import session_scope
from ingestion.storage.models import IngestionRun
from ingestion.storage.postgres_writer import finalize_ingestion_run
from ingestion.validation.validators import RESOLVABLE_ENTITY_TYPES


def run_pipeline(input_path: str, source_override: str | None = None) -> IngestionSummary:
    start = time.monotonic()
    graph = build_graph()
    initial_state: PipelineState = {
        "input_path": input_path,
        "source_override": source_override,
        "errors": [],
        "warnings": [],
    }
    final_state = graph.invoke(initial_state)
    duration = time.monotonic() - start

    entities = final_state.get("entities", [])
    relations = final_state.get("relations", [])
    chunks = final_state.get("chunks", [])
    errors = list(final_state.get("errors", []))
    warnings = list(final_state.get("warnings", []))
    document = final_state.get("document")
    pages = final_state.get("pages", [])
    db_document_id = final_state.get("db_document_id")

    entities_by_type = dict(Counter(e.type for e in entities))
    resolvable = [e for e in entities if e.type in RESOLVABLE_ENTITY_TYPES]
    resolved = sum(1 for e in resolvable if e.resolution_status == "RESOLVED")
    unresolved = len(resolvable) - resolved
    embeddings_created = sum(1 for c in chunks if c.embedding)

    if final_state.get("fatal_error") and not db_document_id:
        status = "FAILED"
    elif errors or warnings:
        status = "SUCCESS_WITH_WARNINGS"
    else:
        status = "SUCCESS"

    run_id = final_state.get("db_run_id") or str(uuid.uuid4())

    summary = IngestionSummary(
        run_id=run_id,
        source_path=input_path,
        status=status,
        documents_processed=1 if document else 0,
        pages_processed=len(pages),
        entities_extracted=len(entities),
        entities_by_type=entities_by_type,
        entities_resolved=resolved,
        entities_unresolved=unresolved,
        relations_extracted=len(relations),
        chunks_created=len(chunks),
        embeddings_created=embeddings_created,
        warnings=warnings,
        errors=errors,
        duration_seconds=round(duration, 3),
    )

    settings = get_settings()
    db_run_id = final_state.get("db_run_id")
    if settings.database_url and db_run_id:
        try:
            with session_scope() as session:
                run = session.get(IngestionRun, uuid.UUID(db_run_id))
                if run is not None:
                    finalize_ingestion_run(
                        session, run, status, summary.model_dump(mode="json"),
                        error_count=len(errors), warning_count=len(warnings),
                    )
        except Exception as exc:  # bookkeeping failure shouldn't fail the run
            summary.warnings.append(f"finalize_ingestion_run: {exc}")

    return summary
