"""Simple chunking: section-aware split on heading-like lines when present,
otherwise a fixed-size sliding window with overlap, preferring to cut on a
paragraph/sentence boundary near the target size. No semantic chunking.
"""
from __future__ import annotations

import re

from ingestion.schemas import Chunk, PageRecord

_HEADING_RE = re.compile(r"^\s{0,3}(\d+(\.\d+)*\s+)?[A-Z][A-Za-z /]{3,60}:?$")


def _detect_sections(text: str) -> list[tuple[int, str | None, str]]:
    """Split text into (char_offset, heading_or_None, section_text) blocks
    based on heading-like lines. Falls back to a single section covering
    the whole text when no headings are detected.
    """
    lines = text.split("\n")
    offsets = []
    pos = 0
    for line in lines:
        offsets.append(pos)
        pos += len(line) + 1

    heading_indices = [i for i, line in enumerate(lines) if _HEADING_RE.match(line.strip())]
    if not heading_indices:
        return [(0, None, text)]

    sections: list[tuple[int, str | None, str]] = []
    if heading_indices[0] > 0:
        pre_text = "\n".join(lines[: heading_indices[0]])
        sections.append((0, None, pre_text))

    boundaries = heading_indices + [len(lines)]
    for i, start_line in enumerate(heading_indices):
        end_line = boundaries[i + 1]
        heading = lines[start_line].strip()
        section_text = "\n".join(lines[start_line:end_line])
        sections.append((offsets[start_line], heading, section_text))

    return sections


def _fixed_size_chunks(text: str, max_chars: int, overlap: int) -> list[tuple[int, int, str]]:
    if not text.strip():
        return []
    if len(text) <= max_chars:
        return [(0, len(text), text.strip())]

    chunks: list[tuple[int, int, str]] = []
    start = 0
    while start < len(text):
        end = min(start + max_chars, len(text))
        if end < len(text):
            cut = text.rfind("\n\n", start, end)
            if cut <= start:
                cut = text.rfind(". ", start, end)
            if cut > start:
                end = cut + 1
        chunk_text = text[start:end].strip()
        if chunk_text:
            chunks.append((start, end, chunk_text))
        if end >= len(text):
            break
        start = max(end - overlap, start + 1)
    return chunks


def chunk_document(pages: list[PageRecord], max_chars: int = 1200, overlap: int = 150) -> list[Chunk]:
    chunks: list[Chunk] = []
    chunk_index = 0
    for page in pages:
        text = page.cleaned_text or page.raw_text or ""
        if not text.strip():
            continue
        for section_offset, heading, section_text in _detect_sections(text):
            for rel_start, rel_end, chunk_text in _fixed_size_chunks(section_text, max_chars, overlap):
                chunks.append(Chunk(
                    chunk_index=chunk_index,
                    page_number=page.page_number,
                    section=heading,
                    text=chunk_text,
                    char_start=section_offset + rel_start,
                    char_end=section_offset + rel_end,
                ))
                chunk_index += 1
    return chunks
