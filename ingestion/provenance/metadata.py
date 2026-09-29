"""Centralizes provenance construction so every extracted fact is
traceable back to its source. Provenance is stored via the existing
`source` (extractor name) and `run_id` columns already on
extracted_entities/extracted_relations -- this module doesn't introduce a
separate provenance table, it just keeps the shape consistent.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

from ingestion.schemas import Entity


@dataclass
class ProvenanceMetadata:
    source_file: str
    run_id: str
    extractor_name: str
    page: int | None = None
    char_span: tuple[int, int] | None = None
    ocr_confidence: float | None = None
    extraction_timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    handwriting_classification: str | None = None
    handwriting_confidence: float | None = None
    handwriting_ocr_provider: str | None = None
    source_content_type: str | None = None

    def as_dict(self) -> dict:
        d = {
            "source": self.source_file,
            "run_id": self.run_id,
            "method": self.extractor_name,
            "page": self.page,
            "char_span": list(self.char_span) if self.char_span else None,
            "ocr_confidence": self.ocr_confidence,
            "extraction_timestamp": self.extraction_timestamp.isoformat(),
        }
        if self.handwriting_classification:
            d["handwriting_classification"] = self.handwriting_classification
            d["handwriting_confidence"] = self.handwriting_confidence
            d["source_content_type"] = self.source_content_type
            if self.handwriting_ocr_provider:
                d["handwriting_ocr_provider"] = self.handwriting_ocr_provider
        return d


def provenance_for_entity(source_file: str, run_id: str, entity: Entity,
                           ocr_confidence: float | None = None) -> ProvenanceMetadata:
    return ProvenanceMetadata(
        source_file=source_file, run_id=run_id, extractor_name=entity.source,
        page=entity.page, char_span=(entity.start, entity.end),
        ocr_confidence=ocr_confidence,
    )
