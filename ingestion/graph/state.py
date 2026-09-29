"""Shared state threaded through every LangGraph node. A plain TypedDict --
each node reads what it needs and returns a partial-state dict that
LangGraph merges (by key overwrite) into the running state.
"""
from __future__ import annotations

from typing import Any, TypedDict

from ingestion.schemas import Chunk, DocumentRecord, Entity, PageRecord, Relation, ValidationResult


class PipelineState(TypedDict, total=False):
    input_path: str
    source_override: str | None
    source_type: str | None
    document: DocumentRecord | None
    pages: list[PageRecord]
    entities: list[Entity]
    relations: list[Relation]
    validation_results: list[ValidationResult]
    chunks: list[Chunk]
    errors: list[str]
    warnings: list[str]
    run_id: str
    needs_ocr: bool
    fatal_error: bool
    db_run_id: str | None
    db_document_id: str | None
    # Internal working data: PDF pages flagged for OCR, carrying their
    # rendered image bytes -- populated by extract_text_node, consumed by
    # ocr_fallback_node. Not part of the pipeline's public output.
    _ocr_pending: list[dict[str, Any]]
    # Handwriting detection results per page
    handwriting_detections: list[Any]
