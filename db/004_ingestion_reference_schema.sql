-- =====================================================================
-- DEMO SUBSTITUTE for the real SODIR/Volve normalized schema.
--
-- This is a minimal, hand-seeded reference dataset used ONLY to give the
-- entity resolver real canonical IDs to resolve extracted entities against
-- in this hackathon demo. It is NOT a faithful reproduction of the SODIR
-- factpages or Volve dataset schema and MUST be replaced with the real
-- normalized SODIR/Volve tables before any production use.
-- =====================================================================

CREATE TABLE IF NOT EXISTS ref_companies (
    company_id      SERIAL PRIMARY KEY,
    name            TEXT NOT NULL UNIQUE,       -- canonical display name, e.g. 'Equinor'
    short_name      TEXT,                       -- e.g. 'Equinor ASA'
    country         TEXT
);

CREATE TABLE IF NOT EXISTS ref_licences (
    licence_id      SERIAL PRIMARY KEY,
    licence_name    TEXT NOT NULL UNIQUE,       -- canonical form, e.g. 'PL 123'
    operator_id     INTEGER REFERENCES ref_companies(company_id),
    status          TEXT DEFAULT 'ACTIVE'
);

CREATE TABLE IF NOT EXISTS ref_fields (
    field_id        SERIAL PRIMARY KEY,
    name            TEXT NOT NULL UNIQUE,
    licence_id      INTEGER REFERENCES ref_licences(licence_id)
);

CREATE TABLE IF NOT EXISTS ref_wells (
    well_id         SERIAL PRIMARY KEY,
    well_name       TEXT NOT NULL UNIQUE,       -- canonical NPD-style form, e.g. '30/6-1'
    field_id        INTEGER REFERENCES ref_fields(field_id),
    licence_id      INTEGER REFERENCES ref_licences(licence_id),
    operator_id     INTEGER REFERENCES ref_companies(company_id)
);

-- Seed rows matching the pipeline's test fixture (well "30/6-1",
-- licence "PL 123", operator "Equinor") so the demo is resolvable end-to-end.
INSERT INTO ref_companies (name, short_name, country) VALUES
    ('Equinor', 'Equinor ASA', 'Norway'),
    ('Shell', 'Shell plc', 'United Kingdom')
ON CONFLICT (name) DO NOTHING;

INSERT INTO ref_licences (licence_name, operator_id, status) VALUES
    ('PL 123', (SELECT company_id FROM ref_companies WHERE name = 'Equinor'), 'ACTIVE')
ON CONFLICT (licence_name) DO NOTHING;

INSERT INTO ref_fields (name, licence_id) VALUES
    ('Volve', (SELECT licence_id FROM ref_licences WHERE licence_name = 'PL 123'))
ON CONFLICT (name) DO NOTHING;

INSERT INTO ref_wells (well_name, field_id, licence_id, operator_id) VALUES
    ('30/6-1',
     (SELECT field_id FROM ref_fields WHERE name = 'Volve'),
     (SELECT licence_id FROM ref_licences WHERE licence_name = 'PL 123'),
     (SELECT company_id FROM ref_companies WHERE name = 'Equinor'))
ON CONFLICT (well_name) DO NOTHING;
