"""pgvector persistence for document chunks, plus a similarity_search
helper for future reuse by the (not-yet-built) LangGraph QA workflow --
not wired into this ingestion CLI.
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from ingestion.schemas import Chunk
from ingestion.storage.models import DocumentChunk


def insert_chunk_embeddings(session: Session, document_id, chunks: list[Chunk]) -> list[DocumentChunk]:
    rows = []
    for chunk in chunks:
        row = DocumentChunk(
            document_id=document_id, page_number=chunk.page_number,
            chunk_index=chunk.chunk_index, section=chunk.section, text=chunk.text,
            char_start=chunk.char_start, char_end=chunk.char_end,
            embedding=chunk.embedding, created_at=datetime.now(timezone.utc),
        )
        session.add(row)
        rows.append(row)
    session.flush()
    return rows


def similarity_search(session: Session, query_embedding: list[float], k: int = 5) -> list[DocumentChunk]:
    return (
        session.query(DocumentChunk)
        .order_by(DocumentChunk.embedding.cosine_distance(query_embedding))
        .limit(k)
        .all()
    )
