"""SQLAlchemy ORM models mirroring migrations/*.sql. Migrations remain the
source of truth for schema creation (CREATE EXTENSION, vector type, seed
data); these models are for application-code reads/writes only.
"""
from __future__ import annotations

import uuid
from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import Boolean, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

EMBEDDING_DIM = 384


class Base(DeclarativeBase):
    pass


# ---------------------------------------------------------------------
# DEMO SUBSTITUTE for the real SODIR/Volve schema -- see
# migrations/001_init_reference_schema.sql for the disclaimer.
# ---------------------------------------------------------------------


class RefCompany(Base):
    __tablename__ = "ref_companies"

    company_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    short_name: Mapped[str | None] = mapped_column(Text)
    country: Mapped[str | None] = mapped_column(Text)


class RefLicence(Base):
    __tablename__ = "ref_licences"

    licence_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    licence_name: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    operator_id: Mapped[int | None] = mapped_column(ForeignKey("ref_companies.company_id"))
    status: Mapped[str | None] = mapped_column(Text, default="ACTIVE")


class RefField(Base):
    __tablename__ = "ref_fields"

    field_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    licence_id: Mapped[int | None] = mapped_column(ForeignKey("ref_licences.licence_id"))


class RefWell(Base):
    __tablename__ = "ref_wells"

    well_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    well_name: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    field_id: Mapped[int | None] = mapped_column(ForeignKey("ref_fields.field_id"))
    licence_id: Mapped[int | None] = mapped_column(ForeignKey("ref_licences.licence_id"))
    operator_id: Mapped[int | None] = mapped_column(ForeignKey("ref_companies.company_id"))


# ---------------------------------------------------------------------
# Ingestion schema
# ---------------------------------------------------------------------


class IngestionRun(Base):
    __tablename__ = "ingestion_runs"

    run_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source_path: Mapped[str] = mapped_column(Text, nullable=False)
    source_type: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text, nullable=False, default="RUNNING")
    started_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))
    error_count: Mapped[int] = mapped_column(Integer, default=0)
    warning_count: Mapped[int] = mapped_column(Integer, default=0)
    summary_json: Mapped[dict | None] = mapped_column(JSONB)


class Document(Base):
    __tablename__ = "documents"

    document_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    run_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("ingestion_runs.run_id"))
    file_name: Mapped[str] = mapped_column(Text, nullable=False)
    file_hash: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    source_type: Mapped[str] = mapped_column(Text, nullable=False)
    page_count: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))

    pages: Mapped[list["DocumentPage"]] = relationship(back_populates="document", cascade="all, delete-orphan")
    chunks: Mapped[list["DocumentChunk"]] = relationship(back_populates="document", cascade="all, delete-orphan")


class DocumentPage(Base):
    __tablename__ = "document_pages"

    page_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("documents.document_id"), nullable=False)
    page_number: Mapped[int] = mapped_column(Integer, nullable=False)
    raw_text: Mapped[str | None] = mapped_column(Text)
    cleaned_text: Mapped[str | None] = mapped_column(Text)
    used_ocr: Mapped[bool] = mapped_column(Boolean, default=False)
    ocr_confidence: Mapped[float | None] = mapped_column(Float)
    handwriting_classification: Mapped[str | None] = mapped_column(Text)
    handwriting_confidence: Mapped[float | None] = mapped_column(Float)
    handwriting_ocr_status: Mapped[str | None] = mapped_column(Text)
    source_content_type: Mapped[str | None] = mapped_column(Text)

    document: Mapped["Document"] = relationship(back_populates="pages")


class DocumentChunk(Base):
    __tablename__ = "document_chunks"

    chunk_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("documents.document_id"), nullable=False)
    page_number: Mapped[int | None] = mapped_column(Integer)
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    section: Mapped[str | None] = mapped_column(Text)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    char_start: Mapped[int | None] = mapped_column(Integer)
    char_end: Mapped[int | None] = mapped_column(Integer)
    embedding: Mapped[list[float] | None] = mapped_column(Vector(EMBEDDING_DIM))
    created_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))

    document: Mapped["Document"] = relationship(back_populates="chunks")


class ExtractedEntity(Base):
    __tablename__ = "extracted_entities"

    entity_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("documents.document_id"), nullable=False)
    run_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("ingestion_runs.run_id"))
    entity_type: Mapped[str] = mapped_column(Text, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    normalized_value: Mapped[str | None] = mapped_column(Text)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    page_number: Mapped[int | None] = mapped_column(Integer)
    start_char: Mapped[int | None] = mapped_column(Integer)
    end_char: Mapped[int | None] = mapped_column(Integer)
    source: Mapped[str | None] = mapped_column(Text)
    resolution_status: Mapped[str] = mapped_column(Text, nullable=False, default="UNRESOLVED")
    resolved_well_id: Mapped[int | None] = mapped_column(ForeignKey("ref_wells.well_id"))
    resolved_field_id: Mapped[int | None] = mapped_column(ForeignKey("ref_fields.field_id"))
    resolved_licence_id: Mapped[int | None] = mapped_column(ForeignKey("ref_licences.licence_id"))
    resolved_company_id: Mapped[int | None] = mapped_column(ForeignKey("ref_companies.company_id"))
    created_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))


class ExtractedRelation(Base):
    __tablename__ = "extracted_relations"

    relation_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("documents.document_id"), nullable=False)
    run_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("ingestion_runs.run_id"))
    relation_type: Mapped[str] = mapped_column(Text, nullable=False)
    subject_entity_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("extracted_entities.entity_id"))
    object_entity_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("extracted_entities.entity_id"))
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    page_number: Mapped[int | None] = mapped_column(Integer)
    source: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))


class ValidationResultRow(Base):
    __tablename__ = "validation_results"

    validation_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    run_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("ingestion_runs.run_id"))
    document_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("documents.document_id"))
    rule_name: Mapped[str] = mapped_column(Text, nullable=False)
    severity: Mapped[str] = mapped_column(Text, nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    context_json: Mapped[dict | None] = mapped_column(JSONB)
    created_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))
