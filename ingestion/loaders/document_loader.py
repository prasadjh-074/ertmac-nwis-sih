"""Loads a raw document from disk into a DocumentRecord shell (no text
extraction yet -- that happens in preprocessing/ocr).
"""
from __future__ import annotations

import hashlib
from pathlib import Path

from ingestion.schemas import DocumentRecord, SourceType


def load_document(file_path: str, source_type: SourceType) -> DocumentRecord:
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"Input document not found: {file_path}")

    data = path.read_bytes()
    file_hash = hashlib.sha256(data).hexdigest()

    return DocumentRecord(
        file_path=str(path),
        file_name=path.name,
        file_hash=file_hash,
        source_type=source_type,
        pages=[],
    )
