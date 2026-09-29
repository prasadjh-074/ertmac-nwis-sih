"""Tesseract-based OCRProvider (default/only OCR implementation for this
demo). Applies lightweight image preprocessing (grayscale, contrast,
autocontrast) before OCR -- no elaborate CV pipeline.

Fails gracefully: if the tesseract binary or pytesseract package isn't
available, extract_text() returns an OCRResult with error set instead of
raising, so the pipeline can continue (with a warning) rather than crash.
"""
from __future__ import annotations

import io
import logging

from ingestion.config import get_settings
from ingestion.ocr.ocr_provider import OCRProvider
from ingestion.schemas import OCRResult

logger = logging.getLogger(__name__)

_INSTALL_MESSAGE = (
    "Tesseract OCR is not available. Install the binary (e.g. "
    "`brew install tesseract` on macOS) and the Python binding "
    "(`pip install pytesseract`), or set OCR_ENABLED=false to skip OCR."
)


class TesseractOCRProvider(OCRProvider):
    def __init__(self, language: str | None = None):
        settings = get_settings()
        self.language = language or settings.ocr_language

    def _preprocess(self, image):
        from PIL import ImageOps

        image = image.convert("L")  # grayscale
        image = ImageOps.autocontrast(image)
        return image

    def extract_text(self, image_bytes: bytes, page: int | None = None) -> OCRResult:
        settings = get_settings()
        if not settings.ocr_enabled:
            return OCRResult(
                text="", confidence=0.0, page=page, error="OCR_ENABLED is false"
            )

        try:
            import pytesseract
            from PIL import Image
        except ImportError as exc:
            logger.warning(_INSTALL_MESSAGE)
            return OCRResult(text="", confidence=0.0, page=page, error=str(exc))

        try:
            image = Image.open(io.BytesIO(image_bytes))
            image = self._preprocess(image)
            data = pytesseract.image_to_data(
                image, lang=self.language, output_type=pytesseract.Output.DICT
            )
        except pytesseract.TesseractNotFoundError as exc:
            logger.warning(_INSTALL_MESSAGE)
            return OCRResult(text="", confidence=0.0, page=page, error=str(exc))
        except Exception as exc:  # pragma: no cover - defensive, engine-specific
            logger.warning("OCR failed for page %s: %s", page, exc)
            return OCRResult(text="", confidence=0.0, page=page, error=str(exc))

        words = [w for w in data.get("text", []) if w.strip()]
        confidences = [
            float(c) for c in data.get("conf", []) if c not in ("-1", -1)
        ]
        text = " ".join(words)
        mean_confidence = sum(confidences) / len(confidences) if confidences else 0.0

        return OCRResult(text=text, confidence=mean_confidence, page=page)
