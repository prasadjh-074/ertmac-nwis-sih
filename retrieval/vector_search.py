"""
Core pgvector cosine-distance search against geointelligence.window_embeddings
and geointelligence.well_embeddings. This is the only module that talks to
PostgreSQL directly; hybrid_search.py builds on top of it.

Every metadata filter is compiled into the SQL WHERE clause (via
retrieval.filters) and executed by the database, then LIMIT top_k is applied
in SQL too - nothing is over-fetched and filtered in Python.
"""

from typing import List, Optional, Sequence, Tuple

import psycopg2

from db_config import get_db_config

from .filters import WindowFilters, WellFilters, build_where_clause
from .ranking import WindowResult, WellResult, rank_window_rows, rank_well_rows

DB_CONFIG = get_db_config()

# The only embedding_type currently loaded into geointelligence (see
# load_embeddings_reduced.py) - the FROZEN, leakage-reduced 30-dim variant.
EMBEDDING_TYPE = "core_reduced"

_dimension_cache = {}


class InvalidVectorDimensionError(ValueError):
    """Raised when a query vector's length does not match the embedding
    dimension actually stored in the database."""


def get_connection():
    return psycopg2.connect(**DB_CONFIG)


def to_vector_literal(vector: Sequence[float]) -> str:
    """pgvector text input format: '[v1,v2,...]'."""
    return "[" + ",".join(repr(float(v)) for v in vector) + "]"


def parse_vector_literal(raw) -> List[float]:
    """psycopg2 (without the optional pgvector adapter) returns a vector
    column as its text form, e.g. '[0.1,-0.2,...]'. Parse it back to a
    plain list of floats."""

    if isinstance(raw, (list, tuple)):
        return [float(v) for v in raw]
    return [float(v) for v in raw.strip("[]").split(",")]


def get_embedding_dimension(conn=None) -> int:
    """Discover the embedding dimension from the data itself (cached after
    the first call) rather than hard-coding it in this module."""

    if "dim" in _dimension_cache:
        return _dimension_cache["dim"]

    own_conn = conn is None
    if own_conn:
        conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT vector_dims(embedding) FROM geointelligence.window_embeddings "
                "WHERE embedding_type = %s LIMIT 1;",
                (EMBEDDING_TYPE,),
            )
            row = cur.fetchone()
            if row is None:
                raise RuntimeError(
                    "No rows in geointelligence.window_embeddings - cannot determine embedding dimension"
                )
            _dimension_cache["dim"] = row[0]
    finally:
        if own_conn:
            conn.close()

    return _dimension_cache["dim"]


def _validate_query_vector(vector: Sequence[float], conn=None) -> None:
    expected_dim = get_embedding_dimension(conn)
    if len(vector) != expected_dim:
        raise InvalidVectorDimensionError(
            f"query_vector has {len(vector)} dimensions, expected {expected_dim}"
        )


def _execute_exact_vector_query(conn, sql: str, params: list) -> list:
    """Execute a pgvector `<=>` query with the ANN index disabled for this
    statement, forcing an exact sequential scan + sort instead of the
    approximate HNSW index scan.

    Why: pgvector's HNSW `ORDER BY ... LIMIT k` plan scans only the index's
    approximate nearest candidates (bounded by hnsw.ef_search, default 40)
    and applies any WHERE filter AFTER that scan, not before. Verified with
    EXPLAIN ANALYZE during development: `WHERE dataset = 'VOLVE'` (an 8% Volve
    slice among ~90% FORCE_2020 rows) returned ZERO rows through the index
    plan (all 40 approximate candidates were FORCE_2020 and got filtered
    out), even though 1,487 real VOLVE rows exist. This is a known pgvector
    "over-filtering" limitation for selective predicates, not a bug in the
    filter SQL itself.

    Fix: force an exact sequential scan for every query in this deterministic
    retrieval library, not just filtered ones, so results are always exactly
    correct rather than sometimes-approximately-correct. At this project's
    scale (tens of thousands of rows), the cost is negligible - ~5-6ms
    measured for a filtered full-table scan+sort, vs sub-millisecond for the
    (sometimes wrong) index plan. The HNSW index still exists on both tables
    (built per instructions) for future use once the row count grows enough
    that this tradeoff needs revisiting.
    """

    with conn.cursor() as cur:
        cur.execute("SET LOCAL enable_indexscan = off;")
        cur.execute("SET LOCAL enable_bitmapscan = off;")
        cur.execute(sql, params)
        rows = cur.fetchall()
    conn.commit()
    return rows


def search_similar_windows(
    query_vector: Sequence[float],
    top_k: int = 10,
    dataset: Optional[str] = None,
    well_id: Optional[str] = None,
    min_curves_present: Optional[int] = None,
    _exclude_window: Optional[Tuple[str, str, int]] = None,
    conn=None,
) -> List[WindowResult]:
    """Nearest-neighbor window search by cosine distance.

    Filters (dataset, well_id, min_curves_present) are compiled into the
    SQL WHERE clause and applied by PostgreSQL before LIMIT top_k - never
    fetched unfiltered and trimmed in Python.
    """

    own_conn = conn is None
    if own_conn:
        conn = get_connection()

    try:
        _validate_query_vector(query_vector, conn)

        filters = WindowFilters(
            dataset=dataset,
            well_id=well_id,
            min_curves_present=min_curves_present,
            exclude_window=_exclude_window,
        )
        clauses, params = filters.to_sql("we")
        clauses.append("we.embedding_type = %s")
        params.append(EMBEDDING_TYPE)
        where_sql = build_where_clause(clauses)

        vec_literal = to_vector_literal(query_vector)

        sql = f"""
            SELECT we.dataset, we.well_id, we.window_id, we.depth_start_m, we.depth_end_m,
                   we.embedding <=> %s::vector AS cosine_distance,
                   we.curves_present, we.embedding_type
            FROM geointelligence.window_embeddings we
            {where_sql}
            ORDER BY we.embedding <=> %s::vector, we.dataset, we.well_id, we.window_id
            LIMIT %s;
        """

        rows = _execute_exact_vector_query(conn, sql, [vec_literal] + params + [vec_literal, top_k])

        return rank_window_rows(rows)
    finally:
        if own_conn:
            conn.close()


def search_similar_wells(
    query_vector: Sequence[float],
    top_k: int = 10,
    dataset: Optional[str] = None,
    min_pooling_fraction: Optional[float] = None,
    _exclude_well: Optional[Tuple[str, str]] = None,
    conn=None,
) -> List[WellResult]:
    """Nearest-neighbor well search by cosine distance."""

    own_conn = conn is None
    if own_conn:
        conn = get_connection()

    try:
        _validate_query_vector(query_vector, conn)

        filters = WellFilters(
            dataset=dataset,
            min_pooling_fraction=min_pooling_fraction,
            exclude_well=_exclude_well,
        )
        clauses, params = filters.to_sql("we")
        clauses.append("we.embedding_type = %s")
        params.append(EMBEDDING_TYPE)
        where_sql = build_where_clause(clauses)

        vec_literal = to_vector_literal(query_vector)

        sql = f"""
            SELECT we.dataset, we.well_id,
                   we.embedding <=> %s::vector AS cosine_distance,
                   we.windows_total, we.windows_pooled, we.windows_excluded, we.pooling_fraction
            FROM geointelligence.well_embeddings we
            {where_sql}
            ORDER BY we.embedding <=> %s::vector, we.dataset, we.well_id
            LIMIT %s;
        """

        rows = _execute_exact_vector_query(conn, sql, [vec_literal] + params + [vec_literal, top_k])

        return rank_well_rows(rows)
    finally:
        if own_conn:
            conn.close()


def fetch_window_vector(dataset: str, well_id: str, window_id: int, conn=None) -> List[float]:
    """Fetch the stored embedding for one window (query-by-example support)."""

    own_conn = conn is None
    if own_conn:
        conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT embedding FROM geointelligence.window_embeddings
                WHERE dataset = %s AND well_id = %s AND window_id = %s AND embedding_type = %s;
                """,
                (dataset, well_id, window_id, EMBEDDING_TYPE),
            )
            row = cur.fetchone()
            if row is None:
                raise LookupError(
                    f"No window embedding found for dataset={dataset!r}, well_id={well_id!r}, window_id={window_id!r}"
                )
            return parse_vector_literal(row[0])
    finally:
        if own_conn:
            conn.close()


def fetch_well_vector(dataset: str, well_id: str, conn=None) -> List[float]:
    """Fetch the stored embedding for one well (query-by-example support)."""

    own_conn = conn is None
    if own_conn:
        conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT embedding FROM geointelligence.well_embeddings
                WHERE dataset = %s AND well_id = %s AND embedding_type = %s;
                """,
                (dataset, well_id, EMBEDDING_TYPE),
            )
            row = cur.fetchone()
            if row is None:
                raise LookupError(f"No well embedding found for dataset={dataset!r}, well_id={well_id!r}")
            return parse_vector_literal(row[0])
    finally:
        if own_conn:
            conn.close()
