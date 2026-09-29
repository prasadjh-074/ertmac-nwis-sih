-- Migration: 003_sodir_knowledge_layer.sql
--
-- Implements the schema additions specified in
-- docs/sodir_knowledge_graph_design.md - and ONLY those additions.
-- Everything else the design relies on (core.well, core.wellbore,
-- core.field, core.discovery, core.company, core.production_licence,
-- core.wellbore_company, subsurface.formation, subsurface.formation_top,
-- subsurface.log_curve/log_measurement) already exists and is untouched
-- by this migration - confirmed empty by direct inspection before writing
-- this file.
--
-- Does NOT touch retrieval.* or geointelligence.* in any way.

-- ============================================================
-- 1. Stratigraphic hierarchy: parent_formation_id
-- ============================================================
-- SODIR's own lsuNpdidLithoStratParent hierarchy (Group -> Formation ->
-- Member), verified present in stratigraphy.parquet / formation_tops.parquet
-- during the design investigation. Self-referential FK, nullable (37/177
-- units are top-level groups with no parent).

ALTER TABLE subsurface.formation
    ADD COLUMN IF NOT EXISTS parent_formation_id BIGINT
        REFERENCES subsurface.formation(formation_id);

CREATE INDEX IF NOT EXISTS idx_formation_parent
    ON subsurface.formation (parent_formation_id);

-- ============================================================
-- 2. Occurrence tables (Wellbore -> observation, matching the exact
--    shape subsurface.formation_top already uses: FK + properties,
--    no separate node identity - per design doc section 4).
-- ============================================================

CREATE TABLE IF NOT EXISTS subsurface.wellbore_history (
    history_id      BIGSERIAL PRIMARY KEY,
    wellbore_id     BIGINT NOT NULL REFERENCES core.wellbore(wellbore_id) ON DELETE CASCADE,
    history_text    TEXT,
    history_date    DATE,
    source_file_id  UUID REFERENCES raw.source_file(file_id),
    metadata        JSONB DEFAULT '{}'::jsonb
);

CREATE INDEX IF NOT EXISTS idx_wellbore_history_wellbore ON subsurface.wellbore_history (wellbore_id);


CREATE TABLE IF NOT EXISTS subsurface.casing (
    casing_id            BIGSERIAL PRIMARY KEY,
    wellbore_id          BIGINT NOT NULL REFERENCES core.wellbore(wellbore_id) ON DELETE CASCADE,
    casing_type          TEXT,
    -- SODIR gives casing/hole diameter as fractional-inch nominal size
    -- notation (e.g. '13 3/8', '9 5/8') - kept as TEXT verbatim rather than
    -- parsed into a float, to avoid silently mis-parsing a fraction.
    casing_diameter      TEXT,
    casing_depth_m       DOUBLE PRECISION,
    hole_diameter        TEXT,
    hole_depth_m         DOUBLE PRECISION,
    formation_test_type  TEXT,
    source_file_id       UUID REFERENCES raw.source_file(file_id),
    metadata             JSONB DEFAULT '{}'::jsonb,
    CONSTRAINT casing_depth_check CHECK (
        casing_depth_m IS NULL OR hole_depth_m IS NULL OR hole_depth_m >= 0
    )
);

CREATE INDEX IF NOT EXISTS idx_casing_wellbore ON subsurface.casing (wellbore_id);

-- Defensive: if this migration was already applied with the earlier
-- (incorrect) DOUBLE PRECISION column type before the fractional-inch
-- string format was discovered, fix it in place rather than dropping data.
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'subsurface' AND table_name = 'casing'
          AND column_name = 'casing_diameter_in'
    ) THEN
        ALTER TABLE subsurface.casing RENAME COLUMN casing_diameter_in TO casing_diameter;
        ALTER TABLE subsurface.casing ALTER COLUMN casing_diameter TYPE TEXT USING casing_diameter::TEXT;
    END IF;
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'subsurface' AND table_name = 'casing'
          AND column_name = 'hole_diameter_in'
    ) THEN
        ALTER TABLE subsurface.casing RENAME COLUMN hole_diameter_in TO hole_diameter;
        ALTER TABLE subsurface.casing ALTER COLUMN hole_diameter TYPE TEXT USING hole_diameter::TEXT;
    END IF;
END $$;


CREATE TABLE IF NOT EXISTS subsurface.dst (
    dst_id                  BIGSERIAL PRIMARY KEY,
    wellbore_id             BIGINT NOT NULL REFERENCES core.wellbore(wellbore_id) ON DELETE CASCADE,
    test_number             TEXT,
    from_depth_m            DOUBLE PRECISION,
    to_depth_m               DOUBLE PRECISION,
    choke_size              DOUBLE PRECISION,
    final_shut_in_pressure  DOUBLE PRECISION,
    final_flow_pressure     DOUBLE PRECISION,
    bottom_hole_pressure    DOUBLE PRECISION,
    downhole_temperature    DOUBLE PRECISION,
    oil_production          DOUBLE PRECISION,
    gas_production          DOUBLE PRECISION,
    source_file_id          UUID REFERENCES raw.source_file(file_id),
    metadata                JSONB DEFAULT '{}'::jsonb,
    CONSTRAINT dst_depth_check CHECK (
        from_depth_m IS NULL OR to_depth_m IS NULL OR to_depth_m >= from_depth_m
    )
);

CREATE INDEX IF NOT EXISTS idx_dst_wellbore ON subsurface.dst (wellbore_id);


CREATE TABLE IF NOT EXISTS subsurface.mud (
    mud_id           BIGSERIAL PRIMARY KEY,
    wellbore_id      BIGINT NOT NULL REFERENCES core.wellbore(wellbore_id) ON DELETE CASCADE,
    track            TEXT,
    md_m             DOUBLE PRECISION,
    mud_weight       DOUBLE PRECISION,
    mud_viscosity    DOUBLE PRECISION,
    yield_point      DOUBLE PRECISION,
    mud_type         TEXT,
    source_file_id   UUID REFERENCES raw.source_file(file_id),
    metadata         JSONB DEFAULT '{}'::jsonb
);

CREATE INDEX IF NOT EXISTS idx_mud_wellbore ON subsurface.mud (wellbore_id);


CREATE TABLE IF NOT EXISTS subsurface.core (
    core_id             BIGSERIAL PRIMARY KEY,
    wellbore_id         BIGINT NOT NULL REFERENCES core.wellbore(wellbore_id) ON DELETE CASCADE,
    core_number         TEXT,
    number_of_cores     DOUBLE PRECISION,
    total_core_length   DOUBLE PRECISION,
    interval_top_m      DOUBLE PRECISION,
    interval_bottom_m   DOUBLE PRECISION,
    sample_available    TEXT,
    source_file_id      UUID REFERENCES raw.source_file(file_id),
    metadata             JSONB DEFAULT '{}'::jsonb,
    CONSTRAINT core_interval_check CHECK (
        interval_top_m IS NULL OR interval_bottom_m IS NULL OR interval_bottom_m >= interval_top_m
    )
);

CREATE INDEX IF NOT EXISTS idx_core_wellbore ON subsurface.core (wellbore_id);


CREATE TABLE IF NOT EXISTS subsurface.cuttings (
    cuttings_id        BIGSERIAL PRIMARY KEY,
    wellbore_id        BIGINT NOT NULL REFERENCES core.wellbore(wellbore_id) ON DELETE CASCADE,
    top_depth_m        DOUBLE PRECISION,
    bottom_depth_m     DOUBLE PRECISION,
    sample_available   TEXT,
    source_file_id     UUID REFERENCES raw.source_file(file_id),
    metadata           JSONB DEFAULT '{}'::jsonb,
    CONSTRAINT cuttings_depth_check CHECK (
        top_depth_m IS NULL OR bottom_depth_m IS NULL OR bottom_depth_m >= top_depth_m
    )
);

CREATE INDEX IF NOT EXISTS idx_cuttings_wellbore ON subsurface.cuttings (wellbore_id);

-- ============================================================
-- 3. FORCE/Volve <-> SODIR identity bridge
-- ============================================================
-- Lives in the (already existing, empty) "graph" schema ONLY - per
-- instructions, reused exclusively for this cross-subsystem link, never
-- for a SODIR-internal relationship (those all belong in core/subsurface,
-- which already exist). Loaded verbatim from
-- data/unified/unified_well_registry.csv (see load_sodir_knowledge_graph.py)
-- - the matches are NOT recomputed here.

CREATE TABLE IF NOT EXISTS graph.well_identity_link (
    dataset              TEXT NOT NULL,
    well_id              TEXT NOT NULL,
    wellbore_id          BIGINT NOT NULL REFERENCES core.wellbore(wellbore_id),
    match_method         TEXT NOT NULL,
    matched_sodir_name   TEXT NOT NULL,
    created_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (dataset, well_id)
);

CREATE INDEX IF NOT EXISTS idx_well_identity_link_wellbore
    ON graph.well_identity_link (wellbore_id);

COMMENT ON TABLE graph.well_identity_link IS
    'FORCE_2020/VOLVE well identity -> SODIR core.wellbore, loaded verbatim '
    'from data/unified/unified_well_registry.csv. Wells with no SODIR match '
    'get no row here - never guessed.';
