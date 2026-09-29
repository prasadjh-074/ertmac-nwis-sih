"""Document chunk semantic search using pgvector cosine distance.

Uses the 384-dimensional sentence-transformer embeddings from the
ingestion pipeline — COMPLETELY SEPARATE from the 30-dim well/window
embeddings. All SQL is parameterized.
"""

from __future__ import annotations

from typing import List, Optional, Sequence

import psycopg2

from db_config import get_db_config

from .filters import DocumentFilters, build_where_clause
from .models import DocumentSearchResult
from .ranking import rank_document_rows

DOCUMENT_EMBEDDING_DIM = 384

DB_CONFIG = get_db_config()


def get_connection():
    return psycopg2.connect(**DB_CONFIG)


def _to_vector_literal(vector: Sequence[float]) -> str:
    return "[" + ",".join(repr(float(v)) for v in vector) + "]"


def _execute_exact_vector_query(conn, sql: str, params: list) -> list:
    """Force an exact sequential scan, bypassing the approximate ivfflat
    index on document_chunks.embedding (db/005_ingestion_pipeline_schema.sql).

    Same rationale as retrieval/vector_search.py's helper of the same
    name: ivfflat's approximate ORDER BY ... LIMIT k plan scans only a
    bounded set of candidate lists and can under-return real matches,
    especially at small row counts. At this project's document-chunk
    scale, an exact scan is negligible cost and always correct.
    """
    with conn.cursor() as cur:
        cur.execute("SET LOCAL enable_indexscan = off;")
        cur.execute("SET LOCAL enable_bitmapscan = off;")
        cur.execute(sql, params)
        rows = cur.fetchall()
    conn.commit()
    return rows


def embed_query(text: str) -> List[float]:
    """Embed a query string using the same sentence-transformer model
    used during ingestion (all-MiniLM-L6-v2, 384 dim)."""
    from ingestion.embeddings.sentence_transformer_embedder import SentenceTransformerEmbedder

    embedder = SentenceTransformerEmbedder()
    vectors = embedder.embed([text])
    return vectors[0]


def search_documents(
    query_text: str,
    top_k: int = 5,
    source_type: Optional[str] = None,
    file_name: Optional[str] = None,
    query_embedding: Optional[List[float]] = None,
    conn=None,
) -> List[DocumentSearchResult]:
    """Semantic search over document chunks.

    Embeds query_text with the sentence-transformer, then runs cosine
    distance search against document_chunks.embedding (384-dim).
    If query_embedding is provided, it is used directly (skipping embed).
    """

    if query_embedding is None:
        query_embedding = embed_query(query_text)

    if len(query_embedding) != DOCUMENT_EMBEDDING_DIM:
        raise ValueError(
            f"Query embedding has {len(query_embedding)} dimensions, "
            f"expected {DOCUMENT_EMBEDDING_DIM}"
        )

    own_conn = conn is None
    if own_conn:
        conn = get_connection()

    try:
        filters = DocumentFilters(source_type=source_type, file_name=file_name)
        clauses, params = filters.to_sql("dc")
        clauses.append("dc.embedding IS NOT NULL")
        where_sql = build_where_clause(clauses)

        vec_literal = _to_vector_literal(query_embedding)

        sql = f"""
            SELECT dc.chunk_id, dc.document_id, d.file_name,
                   dc.page_number, dc.chunk_index, dc.section, dc.text,
                   dc.embedding <=> %s::vector AS cosine_distance
            FROM document_chunks dc
            JOIN documents d ON d.document_id = dc.document_id
            {where_sql}
            ORDER BY dc.embedding <=> %s::vector
            LIMIT %s;
        """

        all_params = [vec_literal] + params + [vec_literal, top_k]

        rows = _execute_exact_vector_query(conn, sql, all_params)

        return rank_document_rows(rows)
    finally:
        if own_conn:
            conn.close()
