"""OCR routing based on handwriting detection.

Routes pages to the appropriate OCR path:
- TYPED / UNKNOWN → existing Tesseract OCR (unchanged)
- HANDWRITTEN / MIXED → handwriting OCR provider if available,
  otherwise marks needs_handwriting_ocr=True

Never silently feeds handwriting through ordinary OCR and pretends
it is reliable.  Confidence thresholds are configurable.
"""

from __future__ import annotations

import logging
from typing import Optional

from .detector import detect_page, detect_regions
from .models import (
    ContentClassification,
    HandwritingDetection,
    HandwritingOCRStatus,
)
from .ocr_provider import HandwritingOCRProvider, HandwritingOCRResult, TesseractHandwritingProvider

logger = logging.getLogger(__name__)

# Only invoke handwriting OCR when detection confidence exceeds this
ROUTING_CONFIDENCE_THRESHOLD = 0.3


def get_default_handwriting_provider() -> Optional[HandwritingOCRProvider]:
    """Return the available handwriting OCR provider, or None.

    Currently returns TesseractHandwritingProvider as the fallback.
    To plug in a better provider, replace this function or configure
    via environment variable.
    """
    try:
        import pytesseract
        pytesseract.get_tesseract_version()
        return TesseractHandwritingProvider()
    except Exception:
        return None


def route_page(
    image_bytes: bytes,
    ocr_data: Optional[dict] = None,
    page_number: int = 1,
    provider: Optional[HandwritingOCRProvider] = None,
    *,
    confidence_threshold: float = ROUTING_CONFIDENCE_THRESHOLD,
) -> HandwritingDetection:
    """Detect handwriting and optionally run handwriting OCR.

    1. Runs detection (always)
    2. If handwriting detected with sufficient confidence:
       a. If provider available → run handwriting OCR
       b. If no provider → mark DETECTED_OCR_UNAVAILABLE
    3. Returns detection with OCR results attached

    The original image is never destroyed.
    """
    detection = detect_page(image_bytes, ocr_data, page_number)

    if not detection.needs_handwriting_ocr:
        return detection

    if detection.confidence < confidence_threshold:
        detection.ocr_status = HandwritingOCRStatus.DETECTION_UNCERTAIN
        detection.needs_handwriting_ocr = False
        return detection

    # Region detection for mixed pages
    if detection.classification == ContentClassification.MIXED and ocr_data:
        detection.regions = detect_regions(image_bytes, ocr_data, page_number)

    # Attempt handwriting OCR
    if provider is None:
        detection.ocr_status = HandwritingOCRStatus.DETECTED_OCR_UNAVAILABLE
        logger.info(
            "Page %d classified as %s but no handwriting OCR provider available",
            page_number, detection.classification.value,
        )
        return detection

    result = provider.extract_handwriting(image_bytes)

    if result.error:
        detection.ocr_status = HandwritingOCRStatus.DETECTED_OCR_UNAVAILABLE
        detection.handwriting_ocr_provider = provider.provider_name
        logger.warning(
            "Handwriting OCR failed on page %d: %s", page_number, result.error,
        )
        return detection

    detection.handwriting_ocr_text = result.text
    detection.handwriting_ocr_confidence = result.confidence
    detection.handwriting_ocr_provider = result.provider

    if result.confidence >= 50.0:
        detection.ocr_status = HandwritingOCRStatus.DETECTED_OCR_SUCCESS
    else:
        detection.ocr_status = HandwritingOCRStatus.DETECTED_OCR_LOW_CONFIDENCE

    return detection
