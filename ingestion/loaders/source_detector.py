"""Detects the source type (pdf/text/image) of an input document."""
from __future__ import annotations

from pathlib import Path

from ingestion.schemas import SourceType

_IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp"}
_TEXT_EXTENSIONS = {".txt", ".md"}

_PDF_MAGIC = b"%PDF-"
_PNG_MAGIC = b"\x89PNG\r\n\x1a\n"
_JPEG_MAGIC = b"\xff\xd8\xff"


def detect_source(file_path: str) -> SourceType:
    """Detect source type by extension first, falling back to magic bytes."""
    ext = Path(file_path).suffix.lower()
    if ext == ".pdf":
        return "pdf"
    if ext in _IMAGE_EXTENSIONS:
        return "image"
    if ext in _TEXT_EXTENSIONS:
        return "text"

    # No/unknown extension -- sniff magic bytes.
    try:
        with open(file_path, "rb") as f:
            header = f.read(8)
    except OSError:
        return "text"

    if header.startswith(_PDF_MAGIC):
        return "pdf"
    if header.startswith(_PNG_MAGIC) or header.startswith(_JPEG_MAGIC):
        return "image"
    return "text"
