"""Handwritten content detection for the ingestion pipeline.

Detects whether scanned/image pages contain typed, handwritten, or
mixed content.  Routes pages to the appropriate OCR path and preserves
detection provenance for downstream NLP/event extraction.
"""

from .models import (
    ContentClassification,
    HandwritingDetection,
    HandwritingOCRStatus,
    HandwritingRegion,
)

__all__ = [
    "ContentClassification",
    "HandwritingDetection",
    "HandwritingOCRStatus",
    "HandwritingRegion",
]
