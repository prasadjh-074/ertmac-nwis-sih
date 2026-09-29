"""Result ranking for document retrieval — cosine similarity only."""

from __future__ import annotations

from typing import List, Sequence, Tuple

from .models import DocumentSearchResult


def rank_document_rows(rows: Sequence[Tuple]) -> List[DocumentSearchResult]:
    """Rows are pre-sorted by cosine distance ascending. Assigns 1-indexed
    rank and converts cosine distance to similarity (1 - distance)."""

    results = []
    for i, row in enumerate(rows, start=1):
        (chunk_id, document_id, file_name, page_number,
         chunk_index, section, text, cosine_distance) = row
        results.append(DocumentSearchResult(
            chunk_id=str(chunk_id),
            document_id=str(document_id),
            file_name=file_name,
            page_number=page_number,
            chunk_index=chunk_index,
            section=section,
            text=text,
            similarity=1.0 - float(cosine_distance),
            rank=i,
        ))
    return results
