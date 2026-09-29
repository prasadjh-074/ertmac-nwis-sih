-- Migration: 001_create_geointelligence_schema.sql
--
-- Creates the "geointelligence" schema and its two pgvector tables for the
-- FROZEN, leakage-reduced (30-dim) core embedding variant produced by
-- build_embeddings_reduced.py from:
--   data/embeddings/window_embeddings_reduced.parquet
--   data/embeddings/well_embeddings_reduced.parquet
--
-- Pre-existing context (discovered by inspection, not touched here):
--   - Database: geo_intelligence, on the Homebrew PostgreSQL 18 instance
--     at localhost:5433 (NOT the separate EDB PostgreSQL 18 on 5432).
--   - pgvector extension 0.8.6 already installed in schema "public".
--   - An unrelated, currently-empty "retrieval" schema already exists
--     (retrieval.document/chunk/embedding/well_embedding/well_similarity),
--     designed around vector(1536) text-chunk embeddings tied to
--     core.wellbore. It is a different subsystem and is left untouched.
--   - This migration only ADDS a new schema; nothing existing is altered.
--
-- The embedding dimension (30) was discovered by inspecting the parquet
-- files at run time (see load_embeddings_reduced.py), not hard-coded here
-- independently of that inspection - this file documents the dimension
-- that inspection found, for a human reader.

CREATE SCHEMA IF NOT EXISTS geointelligence;

-- pgvector's "vector" type lives in the "public" schema (already on the
-- default search_path "$user", public), so it resolves without
-- schema-qualifying it here.

-- ============================================================
-- geointelligence.window_embeddings
-- ============================================================
-- One row per ELIGIBLE window (embedding_eligible = true only - windows
-- that failed the >=4/11 shared-curve-presence gate are never inserted;
-- there is no placeholder/zero vector for them).

CREATE TABLE IF NOT EXISTS geointelligence.window_embeddings (
    id                  BIGSERIAL PRIMARY KEY,
    dataset             TEXT NOT NULL,
    well_id             TEXT NOT NULL,
    window_id           BIGINT NOT NULL,
    depth_start_m       DOUBLE PRECISION,
    depth_end_m         DOUBLE PRECISION,
    embedding_eligible  BOOLEAN NOT NULL,
    curves_present      INTEGER NOT NULL,
    embedding_type      TEXT NOT NULL,
    embedding           VECTOR(30) NOT NULL,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),

    CONSTRAINT window_embeddings_unique_key
        UNIQUE (dataset, well_id, window_id, embedding_type),
    CONSTRAINT window_embeddings_eligible_check
        CHECK (embedding_eligible = TRUE)
);

COMMENT ON TABLE geointelligence.window_embeddings IS
    'Leakage-reduced (30-dim) core window embeddings, retrieval version. '
    'Baseline (35-dim) audit embeddings remain only in '
    'data/embeddings/window_embeddings.parquet and are not loaded here.';

-- ============================================================
-- geointelligence.well_embeddings
-- ============================================================
-- One row per well that had at least one eligible window pooled
-- (mean-pooled, unweighted by dataset/lithology).

CREATE TABLE IF NOT EXISTS geointelligence.well_embeddings (
    id                  BIGSERIAL PRIMARY KEY,
    dataset             TEXT NOT NULL,
    well_id             TEXT NOT NULL,
    embedding_type      TEXT NOT NULL,
    embedding           VECTOR(30) NOT NULL,
    windows_total       INTEGER NOT NULL,
    windows_pooled      INTEGER NOT NULL,
    windows_excluded    INTEGER NOT NULL,
    pooling_fraction    DOUBLE PRECISION NOT NULL,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),

    CONSTRAINT well_embeddings_unique_key
        UNIQUE (dataset, well_id, embedding_type),
    CONSTRAINT well_embeddings_pooled_check
        CHECK (windows_pooled > 0)
);

COMMENT ON TABLE geointelligence.well_embeddings IS
    'Leakage-reduced (30-dim) mean-pooled well embeddings, retrieval version.';

-- ============================================================
-- Indexes
-- ============================================================
-- Plain lookup indexes (safe to create up front - they do not depend on
-- data being loaded).

CREATE INDEX IF NOT EXISTS idx_window_embeddings_dataset_well
    ON geointelligence.window_embeddings (dataset, well_id);

CREATE INDEX IF NOT EXISTS idx_well_embeddings_dataset
    ON geointelligence.well_embeddings (dataset);

-- HNSW cosine-distance vector indexes. Per instructions, these are created
-- AFTER data is loaded (HNSW build quality/time is data-dependent, and
-- building against an empty table is pointless) - see
-- 002_create_vector_indexes.sql, executed by load_embeddings_reduced.py
-- once every row has been inserted and validated.
