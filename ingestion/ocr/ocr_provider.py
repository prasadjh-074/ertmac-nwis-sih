"""OCR abstraction. Swap in a different engine later by implementing a new
OCRProvider -- the rest of the pipeline only depends on this interface.
"""
from __future__ import annotations

from abc import ABC, abstractmethod

from ingestion.schemas import OCRResult


class OCRProvider(ABC):
    @abstractmethod
    def extract_text(self, image_bytes: bytes, page: int | None = None) -> OCRResult:
        """Run OCR on an image (raw bytes, e.g. PNG) and return an OCRResult.

        Must never raise for "OCR unavailable" conditions (missing binary,
        missing language pack, etc.) -- return an OCRResult with `error` set
        and `text=""` instead, so the pipeline can degrade gracefully.
        """
        raise NotImplementedError
