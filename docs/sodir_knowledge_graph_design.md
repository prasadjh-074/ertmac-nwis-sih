# SODIR Geological Knowledge Graph — Design

Status: **design only**. Nothing in this document has been implemented.
No SODIR data was modified, no PostgreSQL schema was created or altered,
no Gemini/LLM/LangGraph work was done. This is a design informed by
directly inspecting the existing canonicalized SODIR outputs, the existing
(currently empty) PostgreSQL schemas, and the existing unified well
registry — not by inventing a schema from scratch.

## 0. What was inspected before writing this

- `data/sodir/processed/*.parquet` (18 canonicalized tables — see §1)
- `data/sodir/schema/sodir_key_inventory.csv`, `sodir_table_inventory.csv`
- `data/sodir/qc/relationship_qc.csv`, `formation_tops_qc.csv`,
  `stratigraphy_qc.csv`, `wellbore_qc.csv`, `canonicalization_summary.csv`
- `canonicalize_sodir.py` (how `*_id` surrogate columns are actually built)
- The live PostgreSQL database (`geo_intelligence`), specifically the
  `core`, `subsurface`, `production`, `graph`, and `retrieval` schemas —
  all of which already exist and are **currently empty (0 rows)**.

**Important correction found during inspection**: `data/sodir/qc/wellbore_qc.csv`
reports `missing_field_id: 9840` and `missing_discovery_id: 9840` (i.e. "all
wellbores"). Directly checking `wellbores.parquet` shows this is wrong —
real null counts are `fldNpdidField`: 2,433/9,840 and `dscNpdidDiscovery`:
1,992/9,840. That QC file appears to have a bug (likely checked the wrong
condition). This design uses the numbers verified directly against the
data, not the stale QC file, and flags the discrepancy rather than
silently using either number.

## 1. Canonical entities

Every one of the 14 requested entity types is already backed by exactly
one canonicalized SODIR table (no gaps, no invented entities):

| Entity | Backing table | Rows | Native SODIR PK |
|---|---|---|---|
| Wellbore | `wellbores.parquet` | 9,840 | `wlbNpdidWellbore` |
| Field | `field.parquet` (+ `field_description.parquet`) | 142 | `fldNpdidField` |
| Discovery | `discovery.parquet` (+ `discovery_description.parquet`) | 648 | `dscNpdidDiscovery` |
| Company | `company.parquet` | 1,034 | `cmpNpdidCompany` |
| Licence | `licence.parquet` | 1,812 | `prlNpdidLicence` |
| Formation Top | `formation_tops.parquet` | 40,281 | none (interval occurrence — see §4) |
| Stratigraphy/Lithology | `stratigraphy.parquet` | 40,281 rows / **177 unique units** | `lsuNpdidLithoStrat` |
| Well Log | `well_logs.parquet` | 20,056 | none (log-run occurrence; **metadata only, no curve values** — already established in the FORCE/Volve work) |
| Well History | `wellbore_history.parquet` | 1,979 | none (one free-text history entry per wellbore) |
| Casing | `wellbore_casing_and_lot.parquet` | 8,741 | none (interval occurrence) |
| DST | `wellbore_dst.parquet` | 1,187 | none (test occurrence, has `wlbDstTestNumber`) |
| Mud | `wellbore_mud.parquet` | 36,714 | none (depth-point measurement, has `wlbTrack`) |
| Core | `wellbore_core.parquet` (+ `wellbore_core_photo.parquet`, `wellbore_core_photo_aggr.parquet`, `wellbore_thin_section.parquet`) | 8,469 | none (has `wlbCoreNumber`) |
| Cuttings | `cuttings.parquet` | 2,236 | none (interval occurrence) |

Every processed table already carries `source_dataset='SODIR'`,
`source_table=<name>`, and a `wellbore_id` (= `wlbNpdidWellbore`) column
added by `canonicalize_sodir.py` — this existing provenance convention is
reused throughout, not replaced (§7).

Out of scope, discovered but not needed: `sodir_table_inventory.csv` lists
111 raw SODIR tables total; only 18 were canonicalized. This design only
draws on those 18 — it does not reach into the other 93 (e.g. seismic
acquisition, facility, licensing-activity tables) since they weren't asked
for and haven't been canonicalized/QC'd.

## 2. Canonical relationships

Relationships that already exist in the canonicalized data, with their QC
status exactly as found (nothing added, nothing assumed clean without a
check):

| Relationship | Direction | FK column | QC status |
|---|---|---|---|
| Wellbore → Field | wellbore.fldNpdidField → field.fldNpdidField | `fldNpdidField` | **Validated, 0 orphans** (`relationship_qc.csv`). 2,433/9,840 wellbores have no field (nullable — many wellbores are dry/exploration, never assigned a field). |
| Wellbore → Discovery | wellbore.dscNpdidDiscovery → discovery.dscNpdidDiscovery | `dscNpdidDiscovery` | **Validated, 0 orphans**. 1,992/9,840 missing. |
| Wellbore → Company (drilling operator) | wellbore.cmpNpdidCompany → company.cmpNpdidCompany | `cmpNpdidCompany` | **Validated, 0 orphans**. 57/9,840 missing. |
| Wellbore → Licence (production licence) | wellbore.prlNpdidProductionLicence → licence.prlNpdidLicence | `prlNpdidProductionLicence` | **Validated, 8 orphans** (non-null values with no matching licence row) + 494/9,840 missing. The 8 orphans are a genuine, unresolved data gap — see §7. |
| Formation Top → Wellbore | formation_tops.wlbNpdidWellbore → wellbores.wlbNpdidWellbore | `wlbNpdidWellbore` | **Validated, 0 orphans**. |
| Stratigraphy → Wellbore | stratigraphy.wlbNpdidWellbore → wellbores.wlbNpdidWellbore | `wlbNpdidWellbore` | **Validated, 0 orphans**. |
| Field → Company (owner) | field.cmpNpdidCompany → company.cmpNpdidCompany | `cmpNpdidCompany` | **Validated, 0 orphans**. |
| Discovery → Field | discovery.fldNpdidField → field.fldNpdidField | `fldNpdidField` | **Validated, 0 orphans**. |
| Discovery → Company | discovery.cmpNpdidCompany → company.cmpNpdidCompany | `cmpNpdidCompany` | **Validated, 0 orphans**. |
| Formation Top → Stratigraphic Unit | formation_tops.lithostrat_id → stratigraphy.lithostrat_id | `lithostrat_id` | **Present in the data, NOT explicitly checked by `relationship_qc.csv`.** Treated as unverified until checked — see §7. |
| Stratigraphic Unit → parent Stratigraphic Unit | stratigraphy.parent_lithostrat_id → stratigraphy.lithostrat_id (self-referential) | `parent_lithostrat_id` | Present in the data (hierarchy: e.g. Group → Formation → Member, via `lsuLevel`). **Not explicitly checked by the existing QC** — see §7. |
| Well Log → Wellbore | well_logs.wlbNpdidWellbore → wellbores.wlbNpdidWellbore | `wlbNpdidWellbore` | Present, **not explicitly checked** by the existing QC. |
| Well History / Casing / DST / Mud / Core / Cuttings → Wellbore | each table's `wlbNpdidWellbore` → wellbores.wlbNpdidWellbore | `wlbNpdidWellbore` | Present in all six tables, **none explicitly checked** by the existing QC (only the two relationships in `relationship_qc.csv`'s original list were verified with orphan counts). |
| Field / Discovery → Wellbore (reference) | field.wlbNpdidWellbore, discovery.wlbNpdidWellbore → wellbores.wlbNpdidWellbore | `wlbNpdidWellbore` | Present in the raw layer's own row shape (each field/discovery row already carries a wellbore reference). Semantics not specified by SODIR's own schema beyond "referenced wellbore" — **not asserted here to mean "discovery well" or "field-defining well" beyond what the column literally is**, to avoid inferring a relationship SODIR didn't itself state. |
| Licence → Company | licence.cmpNpdidCompany → company.cmpNpdidCompany | `cmpNpdidCompany` | Present, **not explicitly checked**. |

No relationship not backed by an actual foreign-key column in the
canonicalized tables is included. In particular: no lithology inference,
no geological correlation between wells, and no synthetic "similar
formation" edges are proposed here — those are exactly the kind of
invented relationship the brief prohibits.

## 3. Primary / foreign keys

The existing `canonicalize_sodir.py` convention is kept exactly as-is: the
native SODIR NPD numeric ID *is* the primary key; the `*_id` columns
(`wellbore_id`, `field_id`, `discovery_id`, `company_id`, `licence_id`,
`lithostrat_id`, `parent_lithostrat_id`) are plain aliases of
`wlbNpdidWellbore` / `fldNpdidField` / `dscNpdidDiscovery` /
`cmpNpdidCompany` / `prlNpdidLicence` / `lsuNpdidLithoStrat` (confirmed by
reading `canonicalize_sodir.py` directly — nothing independently
generated). This design does not introduce a second key scheme; it reuses
this one everywhere.

Tables without a native single-row PK (Formation Top, Well Log, Casing,
DST, Mud, Core, Cuttings, Well History) are occurrences/observations, not
independently-identified entities — see §4.

## 4. Attributes that stay properties, not nodes

Everything that is a scalar fact *about* one of the 14 node/edge types
stays a property — nothing here gets promoted to its own node:

- All dates (`wlbEntryDate`, `prlDateGranted`, `dscDiscoveryYear`, ...)
- All depths (`lsuTopDepth`, `wlbDstFromDepth`, `wlbCoreIntervalTop`, ...)
- All statuses/text (`wlbStatus`, `prlStatus`, `dscCurrentActivityStatus`, ...)
- Geometry (`SHAPE`, `SHAPE_Length`, `SHAPE_Area`) — kept as a property
  on Field/Licence/Discovery, not used for graph structure. It's not
  needed for any of the queries in §9 and dragging WKT geometries through
  a "lightweight" graph adds weight for no query benefit yet.
- URLs, GUIDs, `wlbFormationTestType`, mud weights/viscosities, DST
  pressures/temperatures/production readings, casing diameters — all
  properties of their respective occurrence.
- The company **role** (drilling operator vs. licensee vs. field owner) is
  a property of the *edge* (e.g. `role='DRILLING_OPERATOR'`), not a
  separate node — this already matches the existing, empty
  `core.wellbore_company(wellbore_id, company_id, role, start_date,
  end_date)` junction table found in the database (§6).

**Formation Top, Casing, DST, Mud, Core, Cuttings, Well History are
modeled as edges/occurrence-tables hanging off Wellbore, not as
standalone nodes.** None of them has an independent identity beyond "this
observation, at this wellbore, at this depth/date" — exactly how the
existing (empty) `subsurface.formation_top` table already treats Formation
Top (a table with `wellbore_id`, `formation_id`, `top_depth_m`,
`base_depth_m` — an edge with properties, not a third node). This design
extends that same pattern to the other five, rather than inventing a
richer node-based model SODIR's own data doesn't support.

**Stratigraphic Unit is the one entity from Formation-Top/Stratigraphy
promoted to a real node**, because it has independent, stable identity
(`lsuNpdidLithoStrat`) referenced by *many* formation-top occurrences
across *many* wellbores, plus a genuine self-referential hierarchy
(`lsuNpdidLithoStratParent`) — that's a real graph structure in the
source data, not an invented one.

## 5. Which SODIR relationships can be represented directly

Answered fully by §2's table: **14 of 14 relationships needed to connect
the requested entity set exist directly as FK columns in the already-
canonicalized data.** 8 are already QC-validated with explicit orphan
counts (0 orphans, except Wellbore→Licence with 8); the remaining 6 are
present in the schema but were never explicitly checked by the existing
`relationship_qc.csv` — this design does not upgrade their status beyond
"present, unverified" (§7) since re-running that QC is implementation, not
design.

## 6. Proposed PostgreSQL representation

**Key finding from inspecting the live database**: `geo_intelligence`
already has a fully-designed but **completely empty** relational schema
that covers a large fraction of this graph — discovered, not built by any
prior step in this project:

| Existing (empty) table | Matches SODIR entity |
|---|---|
| `core.well` | Well (SODIR's `wlbWell`, the parent of one or more wellbores/sidetracks) |
| `core.wellbore` | Wellbore |
| `core.field` | Field |
| `core.discovery` | Discovery |
| `core.company` | Company |
| `core.production_licence` | Licence |
| `core.wellbore_company` | the company-*role* junction (§4) |
| `subsurface.formation` | Stratigraphic Unit (flat only — **no parent_id column**, see below) |
| `subsurface.formation_top` | Formation Top (edge table, wellbore_id + formation_id + depths) |
| `subsurface.log_curve` / `log_measurement` | Well Log (structurally fine; SODIR gives us run metadata only, no samples — `log_measurement` would simply stay empty for SODIR-sourced rows) |
| `subsurface.well_trajectory` | (not requested here; unused by this design) |

Every one of these tables already has `source_system`/`source_id` (a
generic multi-source provenance key, not SODIR-specific) plus a
`(source_system, source_id)` **unique constraint** — i.e. it was already
designed to hold rows from more than one source system. That is the exact
mechanism this design uses for provenance (§7) and for the FORCE/Volve
identity bridge (§8), instead of inventing a new one.

**Gaps in the existing schema, proposed as additions (not yet created)**:

- `subsurface.formation` needs a `parent_formation_id BIGINT REFERENCES
  subsurface.formation(formation_id)` column added, to carry SODIR's real
  lithostratigraphic hierarchy (§4). Everything else about that table is
  already sufficient.
- Five new occurrence tables in `subsurface`, following the exact shape
  `subsurface.formation_top` already uses (wellbore_id FK + properties):
  `subsurface.wellbore_history(wellbore_id, history_text, history_date, ...)`,
  `subsurface.casing(wellbore_id, casing_type, casing_diameter, casing_depth_m, hole_depth_m, ...)`,
  `subsurface.dst(wellbore_id, test_number, from_depth_m, to_depth_m, bottom_hole_pressure, ...)`,
  `subsurface.mud(wellbore_id, track, md, mud_weight, mud_type, ...)`,
  `subsurface.core(wellbore_id, core_number, interval_top_m, interval_bottom_m, ...)`,
  `subsurface.cuttings(wellbore_id, top_depth_m, bottom_depth_m, sample_available, ...)`.
  `core_photo`/`thin_section` would be simple child tables of `core`
  (FK on `wellbore_id, core_number`), not separate graph nodes.

**No new schema is proposed for the relational backbone** — it lives in
the existing `core`/`subsurface` schemas, extending what's already there.

**On the empty `graph` schema**: also discovered already provisioned and
unused. This design proposes using it for exactly one thing that doesn't
fit the relational backbone above: the FORCE/Volve ↔ SODIR identity
bridge (§8), since that's a cross-cutting link between two independently
loaded subsystems (`geointelligence.*` and `core.wellbore`), not a normal
SODIR-internal FK.

**Why no Neo4j / no generic edge-list table**: at this data volume
(9,840 wellbores, ~40k formation tops, 128 embedded wells) a normal
FK-based relational schema plus recursive CTEs gives full graph
traversal — including the Stratigraphic Unit parent chain (§9) — with no
separate graph engine and no flattened `(node_id, edge_type, target_id)`
table duplicating what the FKs above already express. That duplication is
exactly what "do not duplicate the existing schema" argues against. If a
future phase needs schema-free traversal (e.g. an LLM agent walking
arbitrary hops) or true graph algorithms (shortest path, centrality),
that would justify Apache AGE or Neo4j then — not speculatively now.

## 7. Provenance strategy

Reuses the convention `canonicalize_sodir.py` already established, mapped
onto the existing schema's `(source_system, source_id)` columns:

- Every row sourced from SODIR: `source_system = 'SODIR'`,
  `source_id = str(<native NPD id>)` (e.g. `wlbNpdidWellbore`).
- Unverified relationships stay unverified, explicitly. This design does
  **not** upgrade the 6 relationships in §2 lacking an explicit QC check to
  "validated" - a future implementation step should run the same
  orphan-count check `canonicalize_sodir.py` already applied to the other
  8, before relying on them.
- The 8 orphaned `Wellbore → Licence` rows and the `wellbore_qc.csv`
  discrepancy found in §0 are recorded here as **known, unresolved data
  gaps** - not silently dropped, not silently "fixed" by guessing a
  licence.

## 8. FORCE / Volve identity bridge

This project already computed real, inspectable well-name matches in
`data/unified/unified_well_registry.csv` (built while constructing the
unified analytical layer) — **this design reuses that result verbatim, it
does not recompute or re-guess matches**:

- **125 / 131** embedded wells already have a `source_well_id` (a SODIR
  `wlbNpdidWellbore`): 113/118 FORCE_2020, 12/13 Volve.
- Match method (already implemented, not new): exact name match first;
  otherwise the SODIR wellbore name matched as a leading token of the
  FORCE well_id (which carries a free-text field-name suffix SODIR's own
  names don't have).

Proposed representation — `graph.well_identity_link`:

```
dataset          TEXT NOT NULL,   -- 'FORCE_2020' | 'VOLVE'
well_id          TEXT NOT NULL,   -- geointelligence.window_embeddings.well_id
wellbore_id      BIGINT NOT NULL REFERENCES core.wellbore(wellbore_id),
match_method     TEXT NOT NULL,   -- 'exact_name' | 'prefix_name'
matched_sodir_name TEXT NOT NULL,
PRIMARY KEY (dataset, well_id)
```

Populated directly from `unified_well_registry.csv`'s already-matched
rows - 125 rows, no new matching logic. This is the single join point
connecting `geointelligence.*` to the SODIR graph (§9).

## 9. Unresolved identity mappings

The 6 wells with **no** SODIR match are listed here explicitly, not
guessed at:

| dataset | well_id |
|---|---|
| FORCE_2020 | `16/11-1S T3` |
| FORCE_2020 | `30/3-5S` |
| FORCE_2020 | `34/10-16R` |
| FORCE_2020 | `34/6-1` |
| FORCE_2020 | `34/8-7R` |
| VOLVE | `15/9-19 BT2` |

These get **no row** in `graph.well_identity_link`. Any query that joins
`geointelligence.*` through the bridge to SODIR will simply return no
SODIR context for these six - which is the correct, honest behavior, not
an error to work around. (Plausible reasons, *not* asserted as fact:
sidetrack/re-entry suffixes like `S`/`T3`/`R`/`BT2` that don't match
SODIR's own wellbore-name spelling for that sidetrack, or a genuinely
unregistered/renamed well - resolving this further would require
additional lookup, which is out of scope for this design step.)

## 10. Mapping to retrieval results

The bridge table (§8) is the whole mechanism - one join from an embedding
result to the full SODIR graph:

```sql
-- Given a geointelligence retrieval result, pull its SODIR context
SELECT w.wellbore_name, f.field_name, d.discovery_name, c.company_name AS operator
FROM geointelligence.window_embeddings we
JOIN graph.well_identity_link link
  ON link.dataset = we.dataset AND link.well_id = we.well_id
JOIN core.wellbore w ON w.wellbore_id = link.wellbore_id
LEFT JOIN core.field f ON f.field_id = w.field_id
LEFT JOIN core.discovery d ON d.discovery_id = w.discovery_id
LEFT JOIN core.company c ON c.company_id = (
    SELECT company_id FROM core.wellbore_company
    WHERE wellbore_id = w.wellbore_id AND role = 'DRILLING_OPERATOR' LIMIT 1
)
WHERE we.dataset = 'VOLVE' AND we.well_id = '15/9-F-1' AND we.window_id = 130;
```

This lets the retrieval layer built in the previous step answer, for any
similar-window/similar-well result: *what field/discovery/operator is
this, and what does SODIR actually know about this wellbore* - without
ever touching `geointelligence.*`'s own schema or the embedding tables.

## 11. Example graph queries

All against the *proposed* schema (§6) - none of these have been run,
since nothing is implemented yet.

**A. Formation tops for a wellbore, with stratigraphic parent context:**
```sql
SELECT ft.top_depth_m, ft.base_depth_m, f.formation_name, parent.formation_name AS parent_unit
FROM subsurface.formation_top ft
JOIN subsurface.formation f ON f.formation_id = ft.formation_id
LEFT JOIN subsurface.formation parent ON parent.formation_id = f.parent_formation_id
WHERE ft.wellbore_id = %(wellbore_id)s
ORDER BY ft.top_depth_m;
```

**B. Full stratigraphic hierarchy for a unit (recursive CTE, no Neo4j needed):**
```sql
WITH RECURSIVE chain AS (
    SELECT formation_id, formation_name, parent_formation_id, 0 AS depth
    FROM subsurface.formation WHERE formation_id = %(unit_id)s
    UNION ALL
    SELECT p.formation_id, p.formation_name, p.parent_formation_id, c.depth + 1
    FROM subsurface.formation p JOIN chain c ON p.formation_id = c.parent_formation_id
)
SELECT * FROM chain ORDER BY depth DESC;
```

**C. All wells in the same field/licence as a given well:**
```sql
SELECT sibling.wellbore_name
FROM core.wellbore target
JOIN core.wellbore sibling ON sibling.field_id = target.field_id
WHERE target.wellbore_id = %(wellbore_id)s AND sibling.wellbore_id != target.wellbore_id;
```

**D. Cross-check a vector-similarity result against known SODIR geology**
(the highest-value query for the eventual application - see §9 of the
retrieval design, now closing the loop):
```sql
-- For a window search result pair (query well, similar well), do they
-- share any known SODIR formation tops? A real, source-grounded sanity
-- check on whether an embedding-similarity match aligns with known geology.
SELECT DISTINCT f.formation_name
FROM subsurface.formation_top ft1
JOIN subsurface.formation f ON f.formation_id = ft1.formation_id
JOIN subsurface.formation_top ft2 ON ft2.formation_id = ft1.formation_id
WHERE ft1.wellbore_id = %(query_wellbore_id)s
  AND ft2.wellbore_id = %(similar_wellbore_id)s;
```

**E. Data-availability triage**: which wells retrieved by the embedding
layer have SODIR core/DST data available, as candidates for enrichment
where curve coverage is poor:
```sql
SELECT we.dataset, we.well_id, we.curves_present, link.wellbore_id,
       EXISTS(SELECT 1 FROM subsurface.core c WHERE c.wellbore_id = link.wellbore_id) AS has_core,
       EXISTS(SELECT 1 FROM subsurface.dst d WHERE d.wellbore_id = link.wellbore_id) AS has_dst
FROM geointelligence.window_embeddings we
JOIN graph.well_identity_link link ON link.dataset = we.dataset AND link.well_id = we.well_id
WHERE we.curves_present < 6;
```

**F. Field → wellbores → operator company, for a licence-level rollup:**
```sql
SELECT lic.licence_name, f.field_name, w.wellbore_name, comp.company_name
FROM core.production_licence lic
JOIN core.wellbore w ON w.production_licence_id = lic.licence_id
LEFT JOIN core.field f ON f.field_id = w.field_id
LEFT JOIN core.wellbore_company wc ON wc.wellbore_id = w.wellbore_id AND wc.role = 'DRILLING_OPERATOR'
LEFT JOIN core.company comp ON comp.company_id = wc.company_id
WHERE lic.licence_id = %(licence_id)s;
```

## 12. Summary of design decisions against the constraints

- **No invented relationships**: every edge in §2 traces to a real FK
  column found by direct inspection; 6 are flagged explicitly as
  "present but not yet QC-validated" rather than asserted clean.
- **No inferred geology**: Stratigraphic Unit parent/child comes straight
  from SODIR's own `lsuNpdidLithoStratParent`; no similarity-based or
  correlation-based geological edges are proposed anywhere.
- **Provenance preserved**: reuses the exact `source_dataset`/`source_table`
  /`wellbore_id` convention `canonicalize_sodir.py` already established,
  mapped onto the existing schema's generic `(source_system, source_id)`.
- **Missing relationships preserved**: nullable FKs stay nullable
  (2,433 wellbores with no field, 1,992 with no discovery, etc.); the 6
  unmatched FORCE/Volve wells get no bridge row rather than a guessed one.
- **No duplication of the existing retrieval schema**: the SODIR graph
  lives in `core`/`subsurface` (extending what's already there); the
  FORCE/Volve bridge lives in the separate, already-empty `graph` schema;
  neither touches `retrieval.*` (the unrelated 1536-dim RAG tables) or
  `geointelligence.*` (read-only from this graph's perspective).
- **Lightweight, no Neo4j**: justified in §6 - FK + recursive CTEs cover
  every query in §11 at this data scale.
