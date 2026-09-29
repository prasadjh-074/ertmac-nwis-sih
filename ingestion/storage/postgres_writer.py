"""Relational persistence for the ingestion pipeline. Functions add/flush
on the given Session but deliberately do not commit -- callers control
commit boundaries (see graph/workflow.py: one commit after persist_node,
a second after store_vectors_node, so a vector-store failure doesn't roll
back already-persisted entities/relations).
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from ingestion.schemas import DocumentRecord, Entity, PageRecord, Relation, ValidationResult
from ingestion.storage.models import (
    Document,
    DocumentPage,
    ExtractedEntity,
    ExtractedRelation,
    IngestionRun,
    ValidationResultRow,
)

_RESOLVED_TABLE_COLUMNS = {
    "ref_wells": "resolved_well_id",
    "ref_fields": "resolved_field_id",
    "ref_licences": "resolved_licence_id",
    "ref_companies": "resolved_company_id",
}


def create_ingestion_run(session: Session, source_path: str, source_type: str | None) -> IngestionRun:
    run = IngestionRun(
        source_path=source_path, source_type=source_type, status="RUNNING",
        started_at=datetime.now(timezone.utc),
    )
    session.add(run)
    session.flush()
    return run


def finalize_ingestion_run(session: Session, run: IngestionRun, status: str,
                            summary_json: dict, error_count: int, warning_count: int) -> None:
    run.status = status
    run.finished_at = datetime.now(timezone.utc)
    run.error_count = error_count
    run.warning_count = warning_count
    run.summary_json = summary_json


def get_or_create_document(session: Session, run_id, document: DocumentRecord) -> Document:
    existing = session.query(Document).filter_by(file_hash=document.file_hash).first()
    if existing is not None:
        return existing
    row = Document(
        run_id=run_id, file_name=document.file_name, file_hash=document.file_hash,
        source_type=document.source_type, page_count=len(document.pages),
        created_at=datetime.now(timezone.utc),
    )
    session.add(row)
    session.flush()
    return row


def insert_pages(session: Session, document_id, pages: list[PageRecord]) -> list[DocumentPage]:
    rows = []
    for page in pages:
        row = DocumentPage(
            document_id=document_id, page_number=page.page_number,
            raw_text=page.raw_text, cleaned_text=page.cleaned_text,
            used_ocr=page.used_ocr, ocr_confidence=page.ocr_confidence,
            handwriting_classification=page.handwriting_classification,
            handwriting_confidence=page.handwriting_confidence,
            handwriting_ocr_status=page.handwriting_ocr_status,
            source_content_type=page.source_content_type,
        )
        session.add(row)
        rows.append(row)
    session.flush()
    return rows


def insert_entities(session: Session, document_id, run_id,
                     entities: list[Entity]) -> dict[int, ExtractedEntity]:
    """Returns a map of python id(entity) -> persisted ExtractedEntity row,
    used by insert_relations to resolve subject/object foreign keys.
    """
    id_map: dict[int, ExtractedEntity] = {}
    for entity in entities:
        resolved_columns = {col: None for col in _RESOLVED_TABLE_COLUMNS.values()}
        if entity.resolution_status == "RESOLVED" and entity.resolved_table in _RESOLVED_TABLE_COLUMNS:
            resolved_columns[_RESOLVED_TABLE_COLUMNS[entity.resolved_table]] = entity.resolved_id

        row = ExtractedEntity(
            document_id=document_id, run_id=run_id, entity_type=entity.type,
            text=entity.text, normalized_value=entity.normalized_value,
            confidence=entity.confidence, page_number=entity.page,
            start_char=entity.start, end_char=entity.end, source=entity.source,
            resolution_status=entity.resolution_status,
            created_at=datetime.now(timezone.utc),
            **resolved_columns,
        )
        session.add(row)
        session.flush()
        id_map[id(entity)] = row
    return id_map


def insert_relations(session: Session, document_id, run_id, relations: list[Relation],
                      entity_id_map: dict[int, ExtractedEntity]) -> list[ExtractedRelation]:
    rows = []
    for relation in relations:
        subject_row = entity_id_map.get(id(relation.subject))
        object_row = entity_id_map.get(id(relation.object))
        row = ExtractedRelation(
            document_id=document_id, run_id=run_id, relation_type=relation.type,
            subject_entity_id=subject_row.entity_id if subject_row else None,
            object_entity_id=object_row.entity_id if object_row else None,
            confidence=relation.confidence, page_number=relation.page,
            source=relation.source, created_at=datetime.now(timezone.utc),
        )
        session.add(row)
        rows.append(row)
    session.flush()
    return rows


def insert_validation_results(session: Session, run_id, document_id,
                               results: list[ValidationResult]) -> list[ValidationResultRow]:
    rows = []
    for result in results:
        row = ValidationResultRow(
            run_id=run_id, document_id=document_id, rule_name=result.rule_name,
            severity=result.severity, message=result.message,
            context_json=result.context, created_at=datetime.now(timezone.utc),
        )
        session.add(row)
        rows.append(row)
    session.flush()
    return rows
