-- 006_drilling_events.sql
-- Stores canonical drilling events extracted from SODIR wellbore history.
-- Events are linked to wells via well_id + dataset and optionally to
-- SODIR wellbore records via sodir_wellbore_id.

CREATE TABLE IF NOT EXISTS subsurface.drilling_event (
    event_id        SERIAL PRIMARY KEY,
    well_id         TEXT NOT NULL,
    dataset         TEXT NOT NULL,
    event_type      TEXT NOT NULL,
    subtype         TEXT,
    depth_start_m   DOUBLE PRECISION,
    depth_end_m     DOUBLE PRECISION,
    formation       TEXT,
    severity        TEXT NOT NULL DEFAULT 'unknown',
    description     TEXT NOT NULL DEFAULT '',

    -- Provenance
    source_type         TEXT NOT NULL,
    source_table        TEXT,
    source_record_id    INTEGER,
    source_document_id  TEXT,
    source_chunk_id     TEXT,
    source_file_name    TEXT,
    extraction_method   TEXT NOT NULL DEFAULT 'unknown',
    extraction_confidence DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    raw_text_snippet    TEXT,

    sodir_wellbore_id   INTEGER,
    metadata_json       JSONB DEFAULT '{}',
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Queries by well
CREATE INDEX IF NOT EXISTS idx_drilling_event_well
    ON subsurface.drilling_event (well_id, dataset);

-- Queries by event type
CREATE INDEX IF NOT EXISTS idx_drilling_event_type
    ON subsurface.drilling_event (event_type);

-- Depth-range queries (find events near a depth)
CREATE INDEX IF NOT EXISTS idx_drilling_event_depth
    ON subsurface.drilling_event (depth_start_m)
    WHERE depth_start_m IS NOT NULL;

-- Formation-based queries
CREATE INDEX IF NOT EXISTS idx_drilling_event_formation
    ON subsurface.drilling_event (formation)
    WHERE formation IS NOT NULL;

-- SODIR link
CREATE INDEX IF NOT EXISTS idx_drilling_event_sodir
    ON subsurface.drilling_event (sodir_wellbore_id)
    WHERE sodir_wellbore_id IS NOT NULL;
