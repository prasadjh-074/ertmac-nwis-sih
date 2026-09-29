"""
Deterministic retrieval library over geointelligence.window_embeddings and
geointelligence.well_embeddings (the FROZEN, leakage-reduced 30-dim core
embedding). Cosine-similarity vector search only - no LLM, no reranking
model, no learned ranking. See README.md for the full design.
"""

from .filters import WindowFilters, WellFilters
from .ranking import WindowResult, WellResult
from .vector_search import (
    InvalidVectorDimensionError,
    get_connection,
    get_embedding_dimension,
    search_similar_windows,
    search_similar_wells,
    fetch_window_vector,
    fetch_well_vector,
)
from .hybrid_search import (
    hybrid_window_search,
    hybrid_well_search,
    search_similar_windows_by_id,
    search_similar_wells_by_id,
)

__all__ = [
    "WindowFilters",
    "WellFilters",
    "WindowResult",
    "WellResult",
    "InvalidVectorDimensionError",
    "get_connection",
    "get_embedding_dimension",
    "search_similar_windows",
    "search_similar_wells",
    "fetch_window_vector",
    "fetch_well_vector",
    "hybrid_window_search",
    "hybrid_well_search",
    "search_similar_windows_by_id",
    "search_similar_wells_by_id",
]
