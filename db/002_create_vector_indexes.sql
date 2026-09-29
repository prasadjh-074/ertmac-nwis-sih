-- Migration: 002_create_vector_indexes.sql
--
-- pgvector HNSW cosine-distance indexes for geointelligence.window_embeddings
-- and geointelligence.well_embeddings.
--
-- Run AFTER data has been loaded (see load_embeddings_reduced.py), per
-- instructions: "Create pgvector cosine-distance indexes only after
-- loading the data." Building HNSW against an empty table wastes nothing
-- functionally, but the whole point of building it after load is to index
-- the real data in one pass rather than incrementally during insert.
--
-- HNSW (not IVFFlat) is used because it does not require choosing a
-- number-of-lists parameter ahead of time and gives good recall at this
-- prototype's scale (~17.8k window vectors, ~128 well vectors) with
-- default build parameters (m=16, ef_construction=64).

CREATE INDEX IF NOT EXISTS idx_window_embeddings_vector_cosine
    ON geointelligence.window_embeddings
    USING hnsw (embedding vector_cosine_ops);

CREATE INDEX IF NOT EXISTS idx_well_embeddings_vector_cosine
    ON geointelligence.well_embeddings
    USING hnsw (embedding vector_cosine_ops);
