"""Handwriting OCR provider abstraction.

Defines the interface for handwriting-specific OCR.  If no provider
is available, pages are marked as DETECTED_OCR_UNAVAILABLE — the
system never fakes transcription.

To add a handwriting OCR provider, implement HandwritingOCRProvider
and register it in routing.py.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class HandwritingOCRResult:
    text: str
    confidence: float = 0.0
    provider: str = "none"
    bounding_boxes: list[dict] = field(default_factory=list)
    error: Optional[str] = None
    metadata: dict = field(default_factory=dict)


class HandwritingOCRProvider(ABC):
    """Interface for handwriting-specific OCR engines."""

    @abstractmethod
    def extract_handwriting(
        self,
        image_bytes: bytes,
        region: Optional[tuple[int, int, int, int]] = None,
    ) -> HandwritingOCRResult:
        """Extract text from handwritten content in an image.

        Args:
            image_bytes: Raw image bytes (PNG/JPEG).
            region: Optional (x, y, w, h) bounding box to restrict
                    OCR to a specific region.

        Returns:
            HandwritingOCRResult with text, confidence, and provenance.
            Must never raise — return result with error set instead.
        """
        raise NotImplementedError

    @property
    @abstractmethod
    def provider_name(self) -> str:
        raise NotImplementedError


class TesseractHandwritingProvider(HandwritingOCRProvider):
    """Fallback: uses Tesseract with handwriting-optimized preprocessing.

    Tesseract is not specialized for handwriting, so results will have
    lower confidence.  This is documented in the output.
    """

    @property
    def provider_name(self) -> str:
        return "tesseract_handwriting_fallback"

    def extract_handwriting(
        self,
        image_bytes: bytes,
        region: Optional[tuple[int, int, int, int]] = None,
    ) -> HandwritingOCRResult:
        try:
            import io

            import pytesseract
            from PIL import Image, ImageFilter, ImageOps
        except ImportError as exc:
            return HandwritingOCRResult(
                text="", confidence=0.0, provider=self.provider_name,
                error=f"Dependencies unavailable: {exc}",
            )

        try:
            image = Image.open(io.BytesIO(image_bytes))

            if region:
                x, y, w, h = region
                image = image.crop((x, y, x + w, y + h))

            # Handwriting-optimized preprocessing
            gray = image.convert("L")
            gray = ImageOps.autocontrast(gray, cutoff=2)
            gray = gray.filter(ImageFilter.MedianFilter(size=3))
            # Increase contrast for faint handwriting
            gray = ImageOps.autocontrast(gray)

            data = pytesseract.image_to_data(
                gray, lang="eng", output_type=pytesseract.Output.DICT,
                config="--psm 6",  # assume uniform block of text
            )

            words = [w for w in data.get("text", []) if w.strip()]
            confidences = [
                float(c) for c in data.get("conf", [])
                if c not in ("-1", -1) and float(c) > 0
            ]

            text = " ".join(words)
            mean_conf = sum(confidences) / len(confidences) if confidences else 0.0

            bboxes = []
            for i, word in enumerate(data.get("text", [])):
                if not word.strip():
                    continue
                if i < len(data.get("left", [])):
                    bboxes.append({
                        "text": word,
                        "x": data["left"][i],
                        "y": data["top"][i],
                        "w": data["width"][i],
                        "h": data["height"][i],
                        "conf": float(data["conf"][i]),
                    })

            return HandwritingOCRResult(
                text=text,
                confidence=round(mean_conf, 1),
                provider=self.provider_name,
                bounding_boxes=bboxes,
                metadata={
                    "word_count": len(words),
                    "note": "Tesseract is not specialized for handwriting — confidence may be lower than for typed text.",
                },
            )

        except Exception as exc:
            return HandwritingOCRResult(
                text="", confidence=0.0, provider=self.provider_name,
                error=str(exc),
            )
