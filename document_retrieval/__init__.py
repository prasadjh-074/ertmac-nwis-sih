"""Document retrieval at query time over ingested document chunks.

Uses the 384-dimensional sentence-transformer embeddings stored in
document_chunks. This is a SEPARATE vector space from the 30-dimensional
well/window embeddings — the two are never mixed.
"""

from .models import DocumentSearchResult
from .search import search_documents, embed_query
from .filters import DocumentFilters
from .ranking import rank_document_rows

__all__ = [
    "DocumentSearchResult",
    "search_documents",
    "embed_query",
    "DocumentFilters",
    "rank_document_rows",
]
