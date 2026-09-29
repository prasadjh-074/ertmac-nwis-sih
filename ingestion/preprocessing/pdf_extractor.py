"""PDF text extraction via PyMuPDF (fitz), with per-page detection of
whether a page needs OCR (i.e. it's a scanned image with little/no
extractable text). Does not perform OCR itself -- see ingestion/ocr/.
"""
from __future__ import annotations

from dataclasses import dataclass

import pymupdf as fitz  # PyMuPDF -- `import fitz` is now a deprecated alias

# Heuristic: pages with fewer than this many extractable characters are
# treated as scanned/image-only and flagged for OCR fallback.
MIN_CHARS_PER_PAGE = 20
RENDER_DPI = 200


@dataclass
class PdfPageExtraction:
    page_number: int  # 1-indexed
    text: str
    needs_ocr: bool
    image_bytes: bytes | None = None  # rendered PNG, populated only when needs_ocr


def extract_pdf(file_path: str) -> list[PdfPageExtraction]:
    """Extract per-page text from a PDF, flagging pages with little/no
    extractable text as needing OCR (and rendering them to PNG for that
    fallback path).
    """
    results: list[PdfPageExtraction] = []
    doc = fitz.open(file_path)
    try:
        for index, page in enumerate(doc):
            page_number = index + 1
            text = page.get_text().strip()
            needs_ocr = len(text) < MIN_CHARS_PER_PAGE
            image_bytes = None
            if needs_ocr:
                pix = page.get_pixmap(dpi=RENDER_DPI)
                image_bytes = pix.tobytes("png")
            results.append(
                PdfPageExtraction(
                    page_number=page_number,
                    text=text,
                    needs_ocr=needs_ocr,
                    image_bytes=image_bytes,
                )
            )
    finally:
        doc.close()
    return results
