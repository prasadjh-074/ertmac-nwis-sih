"""Document retrieval endpoints.

  POST /documents/search   — semantic search over document chunks
                              (384-dim sentence-transformer embeddings,
                              a SEPARATE vector space from the 30-dim
                              well/window embeddings)
  GET  /documents/{id}     — document metadata + handwriting summary

The embedding of the query text runs locally via the same
sentence-transformer used at ingestion — no external service call.
Result rows include the source document's file name and page number
so any downstream fact remains traceable back to a specific page.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import asdict
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Path
from pydantic import BaseModel, Field

from document_retrieval.search import search_documents

from ..deps import get_conn

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/documents", tags=["documents"])


class DocumentSearchRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=500)
    top_k: int = Field(5, ge=1, le=50)
    source_type: Optional[str] = Field(None, description="Filter by source_type: pdf, text, image")
    file_name: Optional[str] = Field(None, max_length=255)


class DocumentChunkResponse(BaseModel):
    chunk_id: str
    document_id: str
    file_name: str
    page_number: Optional[int] = None
    chunk_index: int
    section: Optional[str] = None
    text: str
    similarity: float
    rank: int


class DocumentSearchResponse(BaseModel):
    query: str
    count: int
    results: List[DocumentChunkResponse]


class PageHandwritingSummary(BaseModel):
    page_number: int
    used_ocr: bool
    ocr_confidence: Optional[float] = None
    handwriting_classification: Optional[str] = None
    handwriting_confidence: Optional[float] = None
    handwriting_ocr_status: Optional[str] = None
    source_content_type: Optional[str] = None


class DocumentMetadataResponse(BaseModel):
    document_id: str
    file_name: str
    source_type: str
    page_count: Optional[int] = None
    handwriting_detected: bool = False
    handwriting_page_count: int = 0
    pages: List[PageHandwritingSummary] = Field(default_factory=list)


@router.post("/search", response_model=DocumentSearchResponse)
def documents_search(body: DocumentSearchRequest, conn=Depends(get_conn)):
    try:
        results = search_documents(
            query_text=body.query,
            top_k=body.top_k,
            source_type=body.source_type,
            file_name=body.file_name,
            conn=conn,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        logger.exception("document search failed: %s", exc)
        raise HTTPException(status_code=500, detail="document search failed")

    return DocumentSearchResponse(
        query=body.query,
        count=len(results),
        results=[
            DocumentChunkResponse(
                chunk_id=str(r.chunk_id),
                document_id=str(r.document_id),
                file_name=r.file_name,
                page_number=r.page_number,
                chunk_index=r.chunk_index,
                section=r.section,
                text=r.text,
                similarity=round(r.similarity, 4),
                rank=r.rank,
            )
            for r in results
        ],
    )


def _validate_uuid(raw: str) -> str:
    try:
        return str(uuid.UUID(raw))
    except (ValueError, TypeError):
        raise HTTPException(status_code=400, detail="document_id must be a valid UUID")


@router.get("/{document_id}", response_model=DocumentMetadataResponse)
def get_document_metadata(
    document_id: str = Path(..., description="Document UUID"),
    conn=Depends(get_conn),
):
    doc_uuid = _validate_uuid(document_id)
    cur = conn.cursor()
    cur.execute(
        "SELECT document_id, file_name, source_type, page_count "
        "FROM documents WHERE document_id = %s",
        (doc_uuid,),
    )
    row = cur.fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail=f"document {document_id} not found")

    doc_id, file_name, source_type, page_count = row

    cur.execute(
        "SELECT page_number, used_ocr, ocr_confidence, "
        "handwriting_classification, handwriting_confidence, "
        "handwriting_ocr_status, source_content_type "
        "FROM document_pages WHERE document_id = %s ORDER BY page_number",
        (doc_uuid,),
    )
    pages = [
        PageHandwritingSummary(
            page_number=r[0],
            used_ocr=bool(r[1]),
            ocr_confidence=r[2],
            handwriting_classification=r[3],
            handwriting_confidence=r[4],
            handwriting_ocr_status=r[5],
            source_content_type=r[6],
        )
        for r in cur.fetchall()
    ]

    hw_pages = [
        p for p in pages
        if p.handwriting_classification in ("handwritten", "mixed")
    ]

    return DocumentMetadataResponse(
        document_id=str(doc_id),
        file_name=file_name,
        source_type=source_type,
        page_count=page_count,
        handwriting_detected=len(hw_pages) > 0,
        handwriting_page_count=len(hw_pages),
        pages=pages,
    )
