-- =====================================================================
-- Ingestion pipeline schema: documents, pages, chunks (+pgvector),
-- extracted entities/relations, ingestion runs, validation results.
-- Additive only -- does not touch ref_* (demo stand-in) tables beyond
-- referencing them via nullable foreign keys on extracted_entities.
-- =====================================================================

CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pgcrypto; -- gen_random_uuid()

CREATE TABLE IF NOT EXISTS ingestion_runs (
    run_id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_path     TEXT NOT NULL,
    source_type     TEXT,                       -- 'pdf'|'text'|'image'
    status          TEXT NOT NULL DEFAULT 'RUNNING', -- RUNNING|SUCCESS|SUCCESS_WITH_WARNINGS|FAILED
    started_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    finished_at     TIMESTAMPTZ,
    error_count     INTEGER DEFAULT 0,
    warning_count   INTEGER DEFAULT 0,
    summary_json    JSONB
);

CREATE TABLE IF NOT EXISTS documents (
    document_id     UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id          UUID REFERENCES ingestion_runs(run_id),
    file_name       TEXT NOT NULL,
    file_hash       TEXT NOT NULL,               -- sha256, for dedup
    source_type     TEXT NOT NULL,
    page_count      INTEGER,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (file_hash)
);

CREATE TABLE IF NOT EXISTS document_pages (
    page_id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id     UUID NOT NULL REFERENCES documents(document_id) ON DELETE CASCADE,
    page_number     INTEGER NOT NULL,
    raw_text        TEXT,
    cleaned_text    TEXT,
    used_ocr        BOOLEAN NOT NULL DEFAULT FALSE,
    ocr_confidence  REAL,
    UNIQUE (document_id, page_number)
);

CREATE TABLE IF NOT EXISTS document_chunks (
    chunk_id        UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id     UUID NOT NULL REFERENCES documents(document_id) ON DELETE CASCADE,
    page_number     INTEGER,
    chunk_index     INTEGER NOT NULL,
    section         TEXT,
    text            TEXT NOT NULL,
    char_start      INTEGER,
    char_end        INTEGER,
    embedding       vector(384),                 -- all-MiniLM-L6-v2 dim
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ivfflat index for cosine similarity search (fine for demo-scale data;
-- requires ANALYZE / some rows before it's useful, harmless if empty).
CREATE INDEX IF NOT EXISTS idx_document_chunks_embedding
    ON document_chunks USING ivfflat (embedding vector_cosine_ops) WITH (lists = 10);

CREATE TABLE IF NOT EXISTS extracted_entities (
    entity_id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id         UUID NOT NULL REFERENCES documents(document_id) ON DELETE CASCADE,
    run_id              UUID REFERENCES ingestion_runs(run_id),
    entity_type         TEXT NOT NULL,           -- WELL, FIELD, LICENCE, COMPANY, FORMATION, ...
    text                TEXT NOT NULL,           -- raw surface form
    normalized_value    TEXT,
    confidence          REAL NOT NULL,
    page_number         INTEGER,
    start_char          INTEGER,
    end_char            INTEGER,
    source              TEXT,                    -- extractor name, e.g. 'regex:well_id'
    resolution_status   TEXT NOT NULL DEFAULT 'UNRESOLVED', -- RESOLVED|UNRESOLVED
    resolved_well_id       INTEGER REFERENCES ref_wells(well_id),
    resolved_field_id      INTEGER REFERENCES ref_fields(field_id),
    resolved_licence_id    INTEGER REFERENCES ref_licences(licence_id),
    resolved_company_id    INTEGER REFERENCES ref_companies(company_id),
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS extracted_relations (
    relation_id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id          UUID NOT NULL REFERENCES documents(document_id) ON DELETE CASCADE,
    run_id               UUID REFERENCES ingestion_runs(run_id),
    relation_type         TEXT NOT NULL,          -- HAS_FORMATION, HAS_LICENCE, OPERATED_BY, ...
    subject_entity_id     UUID REFERENCES extracted_entities(entity_id),
    object_entity_id      UUID REFERENCES extracted_entities(entity_id),
    confidence            REAL NOT NULL,
    page_number           INTEGER,
    source                TEXT,
    created_at             TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS validation_results (
    validation_id        UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id               UUID REFERENCES ingestion_runs(run_id),
    document_id          UUID REFERENCES documents(document_id),
    rule_name            TEXT NOT NULL,
    severity             TEXT NOT NULL,           -- INFO|WARNING|ERROR
    message              TEXT NOT NULL,
    context_json         JSONB,
    created_at             TIMESTAMPTZ NOT NULL DEFAULT now()
);
