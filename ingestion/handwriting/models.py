"""Data models for handwriting detection.

ContentClassification is the page/region-level classification.
HandwritingDetection is the full detection result per page.
HandwritingRegion locates handwritten areas inside mixed pages.
HandwritingOCRStatus tracks the OCR processing state.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional


class ContentClassification(str, Enum):
    TYPED = "typed"
    HANDWRITTEN = "handwritten"
    MIXED = "mixed"
    UNKNOWN = "unknown"


class HandwritingOCRStatus(str, Enum):
    NOT_NEEDED = "not_needed"
    DETECTED_OCR_SUCCESS = "detected_ocr_success"
    DETECTED_OCR_LOW_CONFIDENCE = "detected_ocr_low_confidence"
    DETECTED_OCR_UNAVAILABLE = "detected_ocr_unavailable"
    DETECTION_UNCERTAIN = "detection_uncertain"


@dataclass
class HandwritingRegion:
    """A detected handwritten region within a page."""
    region_id: int
    bbox: tuple[int, int, int, int]  # (x, y, width, height)
    classification: ContentClassification
    confidence: float
    area_fraction: float = 0.0


@dataclass
class HandwritingDetection:
    """Full handwriting detection result for a single page."""
    page_number: int
    classification: ContentClassification
    confidence: float
    detection_method: str
    handwritten_fraction: float = 0.0
    typed_fraction: float = 0.0
    needs_handwriting_ocr: bool = False
    ocr_status: HandwritingOCRStatus = HandwritingOCRStatus.NOT_NEEDED
    regions: list[HandwritingRegion] = field(default_factory=list)
    features: dict[str, Any] = field(default_factory=dict)

    document_id: Optional[str] = None
    handwriting_ocr_text: Optional[str] = None
    handwriting_ocr_confidence: Optional[float] = None
    handwriting_ocr_provider: Optional[str] = None
