"""Typed result models for document retrieval."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass
class DocumentSearchResult:
    """One document chunk returned by a semantic search."""

    chunk_id: str
    document_id: str
    file_name: str
    page_number: Optional[int]
    chunk_index: int
    section: Optional[str]
    text: str
    similarity: float
    rank: int
