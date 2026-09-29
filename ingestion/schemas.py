"""Shared data model for the ingestion pipeline. Pydantic models are used
for anything that crosses an I/O boundary (DB rows, JSON summaries); this
keeps validation and serialization consistent across the pipeline.
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

EntityType = str  # kept as str (not a strict enum) so new ontology entries
                   # don't require a code change -- see ontology/entities.yaml

ResolutionStatus = Literal["RESOLVED", "UNRESOLVED"]
Severity = Literal["INFO", "WARNING", "ERROR"]
SourceType = Literal["pdf", "text", "image"]
RunStatus = Literal["RUNNING", "SUCCESS", "SUCCESS_WITH_WARNINGS", "FAILED"]


class Entity(BaseModel):
    type: EntityType
    text: str
    normalized_value: str | None = None
    confidence: float
    page: int | None = None
    start: int
    end: int
    source: str  # e.g. "regex:well_id", "alias:company"
    resolution_status: ResolutionStatus = "UNRESOLVED"
    resolved_id: int | None = None
    resolved_table: str | None = None  # "ref_wells" | "ref_licences" | ...


class Relation(BaseModel):
    type: str  # e.g. "HAS_FORMATION"
    subject: Entity
    object: Entity
    confidence: float
    page: int | None = None
    source: str  # e.g. "proximity:operated_by"


class OCRResult(BaseModel):
    text: str
    confidence: float = 0.0  # 0-100, tesseract mean word confidence
    engine: str = "tesseract"
    page: int | None = None
    error: str | None = None  # set (with text="") when OCR is unavailable/failed


class PageRecord(BaseModel):
    page_number: int
    raw_text: str
    cleaned_text: str | None = None
    used_ocr: bool = False
    ocr_confidence: float | None = None
    handwriting_classification: str | None = None
    handwriting_confidence: float | None = None
    handwriting_ocr_status: str | None = None
    source_content_type: str | None = None


class DocumentRecord(BaseModel):
    file_path: str
    file_name: str
    file_hash: str
    source_type: SourceType
    pages: list[PageRecord] = Field(default_factory=list)


class Chunk(BaseModel):
    chunk_index: int
    page_number: int | None = None
    section: str | None = None
    text: str
    char_start: int
    char_end: int
    embedding: list[float] | None = None


class ValidationResult(BaseModel):
    rule_name: str
    severity: Severity
    message: str
    context: dict = Field(default_factory=dict)


class IngestionSummary(BaseModel):
    run_id: str
    source_path: str
    status: RunStatus
    documents_processed: int = 0
    pages_processed: int = 0
    entities_extracted: int = 0
    entities_by_type: dict[str, int] = Field(default_factory=dict)
    entities_resolved: int = 0
    entities_unresolved: int = 0
    relations_extracted: int = 0
    chunks_created: int = 0
    embeddings_created: int = 0
    warnings: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    duration_seconds: float = 0.0
