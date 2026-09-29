"""
Deterministic hybrid search: cosine-similarity vector search with metadata
filters acting purely as SQL constraints. No weighting formula is
introduced here - ranking is cosine similarity, full stop; filters only
narrow which rows are eligible to be ranked at all.

Also provides query-by-example: fetch a stored window/well's own vector
from PostgreSQL, then search for its nearest neighbors, excluding the
query object itself from the result set.
"""

from typing import List, Optional

from .ranking import WindowResult, WellResult
from .vector_search import (
    EMBEDDING_TYPE,
    fetch_window_vector,
    fetch_well_vector,
    get_connection,
    search_similar_windows,
    search_similar_wells,
)


def hybrid_window_search(
    query_vector,
    top_k: int = 10,
    dataset: Optional[str] = None,
    well_id: Optional[str] = None,
    min_curves_present: Optional[int] = None,
    conn=None,
) -> List[WindowResult]:
    """v1 hybrid window search: cosine similarity ranking; dataset/well_id/
    min_curves_present are hard SQL constraints on the candidate set, not
    weights. This is intentionally identical to search_similar_windows -
    it exists as the documented entry point this stage's spec asks for,
    without inventing a weighting scheme ahead of having a reason to."""

    return search_similar_windows(
        query_vector,
        top_k=top_k,
        dataset=dataset,
        well_id=well_id,
        min_curves_present=min_curves_present,
        conn=conn,
    )


def hybrid_well_search(
    query_vector,
    top_k: int = 10,
    dataset: Optional[str] = None,
    min_pooling_fraction: Optional[float] = None,
    conn=None,
) -> List[WellResult]:
    """v1 hybrid well search: cosine similarity ranking only."""

    return search_similar_wells(
        query_vector,
        top_k=top_k,
        dataset=dataset,
        min_pooling_fraction=min_pooling_fraction,
        conn=conn,
    )


def search_similar_windows_by_id(
    dataset: str,
    well_id: str,
    window_id: int,
    top_k: int = 10,
    dataset_filter: Optional[str] = None,
    well_id_filter: Optional[str] = None,
    min_curves_present: Optional[int] = None,
    conn=None,
) -> List[WindowResult]:
    """Query-by-example: look up this window's own stored vector, then find
    its nearest neighbors. The query window itself is always excluded from
    its own result set.

    dataset_filter/well_id_filter are separate from the query's own
    (dataset, well_id) so callers can, e.g., search only within Volve for
    neighbors of a FORCE window; they default to no extra constraint.
    """

    own_conn = conn is None
    if own_conn:
        conn = get_connection()
    try:
        query_vector = fetch_window_vector(dataset, well_id, window_id, conn=conn)
        return search_similar_windows(
            query_vector,
            top_k=top_k,
            dataset=dataset_filter,
            well_id=well_id_filter,
            min_curves_present=min_curves_present,
            _exclude_window=(dataset, well_id, window_id),
            conn=conn,
        )
    finally:
        if own_conn:
            conn.close()


def search_similar_wells_by_id(
    dataset: str,
    well_id: str,
    top_k: int = 10,
    dataset_filter: Optional[str] = None,
    min_pooling_fraction: Optional[float] = None,
    conn=None,
) -> List[WellResult]:
    """Query-by-example for wells: look up this well's own stored vector,
    then find its nearest-neighbor wells, excluding itself."""

    own_conn = conn is None
    if own_conn:
        conn = get_connection()
    try:
        query_vector = fetch_well_vector(dataset, well_id, conn=conn)
        return search_similar_wells(
            query_vector,
            top_k=top_k,
            dataset=dataset_filter,
            min_pooling_fraction=min_pooling_fraction,
            _exclude_well=(dataset, well_id),
            conn=conn,
        )
    finally:
        if own_conn:
            conn.close()
