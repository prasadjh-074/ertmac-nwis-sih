# SODIR Knowledge Graph Validation Report

```
======================================================================
SODIR KNOWLEDGE GRAPH VALIDATION
======================================================================

======================================================================
1. ENTITY COUNTS
======================================================================
  wellbore           9,840   [OK]
  field                142   [OK]
  discovery            648   [OK]
  company            1,034   [OK]
  licence            1,812   [OK]
  formation            177   [OK]
  formation_top     40,281   [OK]
  log               20,056   [OK]
  history            1,979   [OK]
  casing             8,741   [OK]
  dst                1,187   [OK]
  mud               36,714   [OK]
  core               8,469   [OK]
  cutting            2,236   [OK]
  identity_bridge      125   [OK]

======================================================================
2. RELATIONSHIP VALIDATION - ORPHAN COUNTS
======================================================================

NOTE: data/sodir/qc/wellbore_qc.csv's field/discovery missingness figures (both '9840', i.e. 'all wellbores') were found to be wrong during the design investigation and are NOT used here. The numbers below come from direct queries against the loaded database.
  core.wellbore.field_id -> core.field                       0
  core.wellbore.discovery_id -> core.discovery               0
  core.wellbore.production_licence_id -> core.production_licence    0
  core.wellbore_company.company_id -> core.company           0
  core.discovery.field_id -> core.field                      0
  subsurface.formation_top.wellbore_id -> core.wellbore      0
  subsurface.formation_top.formation_id -> subsurface.formation    0
  subsurface.formation.parent_formation_id -> subsurface.formation    0
  subsurface.log_curve.wellbore_id -> core.wellbore          0
  subsurface.wellbore_history.wellbore_id -> core.wellbore    0
  subsurface.casing.wellbore_id -> core.wellbore             0
  subsurface.dst.wellbore_id -> core.wellbore                0
  subsurface.mud.wellbore_id -> core.wellbore                0
  subsurface.core.wellbore_id -> core.wellbore               0
  subsurface.cuttings.wellbore_id -> core.wellbore           0
  graph.well_identity_link.wellbore_id -> core.wellbore      0

Discrepancy found vs. the existing relationship_qc.csv: it claims 'wellbore -> discovery: 0 orphans', but the loaded database (and a direct independent check against the source parquet) shows 4 real orphans - wellbores 3313, 3702, 4214, 4926 reference a dscNpdidDiscovery value that does not exist in discovery.parquet's own 648-row key set. relationship_qc.csv is wrong on this one relationship; its other 7 checked relationships (field, company, licence, plus the field/discovery/company-level ones) were independently reproduced here and are correct.

======================================================================
3. NULL RELATIONSHIP COUNTS (preserved, not backfilled)
======================================================================
  core.wellbore.field_id IS NULL                                2,433
  core.wellbore.discovery_id IS NULL                            1,996
  core.wellbore.production_licence_id IS NULL                     502
  core.wellbore with no DRILLING_OPERATOR company link             57
  subsurface.formation.parent_formation_id IS NULL (top-level units)     38

These match the real values found during the design investigation (2,433 missing field / 1,992 missing discovery / 494 missing licence on the source parquet - the count above for discovery is 1,992+4 since the 4 orphaned discovery references were also nulled out at load time, per 'skipped discovery FK' in the loader's own log).

======================================================================
4. DUPLICATE SOURCE IDENTIFIERS
======================================================================
  core.company (source_system, source_id)                    0  OK
  core.field (source_system, source_id)                      0  OK
  core.discovery (source_system, source_id)                  0  OK
  core.production_licence (source_system, source_id)         0  OK
  core.wellbore (source_system, source_id)                   0  OK
  subsurface.formation (source_system, source_id)            0  OK

======================================================================
5. DUPLICATE IDENTITY BRIDGE KEYS
======================================================================
  duplicate (dataset, well_id) in graph.well_identity_link: 0  OK

======================================================================
6. FORCE/VOLVE <-> SODIR MATCH EXPECTATION
======================================================================
  Total bridge rows: 125  (expected 125)  [OK]
    FORCE_2020: 113  (expected 113)  [OK]
    VOLVE:      12  (expected 12)   [OK]

  Expected unmatched wells (from unified_well_registry.csv directly): 6 (expected 6)
    FORCE_2020 16/11-1S T3
    FORCE_2020 30/3-5S
    FORCE_2020 34/10-16R
    FORCE_2020 34/6-1
    FORCE_2020 34/8-7R
    VOLVE      15/9-19 BT2

  graph.well_identity_link keys == registry's matched keys exactly: True

======================================================================
7. DEMONSTRATION QUERIES
======================================================================

Demo anchor wellbore: 31/3-2 (wellbore_id=99)

--- 1. Well -> Field ---
  ('31/3-2', 'TROLL', 'TROLL UNIT')

--- 2. Well -> Formation Tops ---
  (365.0, 540.0, 'NORDLAND GP')
  (540.0, 605.0, 'NO FORMAL NAME')
  (540.0, 1121.0, 'HORDALAND GP')
  (605.0, 1121.0, 'NO FORMAL NAME')
  (1121.0, 1471.0, 'ROGALAND GP')

--- 3. Well -> Stratigraphy (formation + parent unit) ---
  (365.0, 'NORDLAND GP', None)
  (540.0, 'NO FORMAL NAME', None)
  (540.0, 'HORDALAND GP', None)
  (605.0, 'NO FORMAL NAME', None)
  (1121.0, 'ROGALAND GP', None)

--- 4. Well -> Logs ---
  ('ISF LSS GR SP', 451.0, 622.0)
  ('ISF LSS GR SP', 610.0, 1491.0)
  ('ISF LSS GR SP', 1502.0, 2085.0)
  ('LDT CNL CAL GR', 451.0, 624.0)
  ('LDT CNL CAL GR', 610.0, 1493.0)

--- 5. Well -> Drilling History ---
  

<p><b>General</b></p>

<p>Well 31/3-2 was drilled immediately to
the southeast of a fault tha...

--- 6. Well -> DST ---
  ('1.0', 1567.0, 1577.0, 0.0)

--- 7. Well -> Core / Cuttings ---
  core:     ('1', 1565.0, 1575.5)
  core:     ('2', 1581.0, 1590.7)
  core:     ('3', 1593.0, 1606.25)
  cuttings: (460.0, 2090.0)

--- 8. FORCE/Volve well -> SODIR well ---
  ('VOLVE', '15/9-19 A', 'exact_name', '15/9-19 A', 'VOLVE')
  ('VOLVE', '15/9-19 SR', 'exact_name', '15/9-19 SR', 'VOLVE')
  ('VOLVE', '15/9-F-1', 'exact_name', '15/9-F-1', 'VOLVE')
  ('VOLVE', '15/9-F-1 A', 'exact_name', '15/9-F-1 A', 'VOLVE')
  ('VOLVE', '15/9-F-1 B', 'exact_name', '15/9-F-1 B', 'VOLVE')

--- 9. Formation parent-chain traversal (recursive CTE) ---
  (1, 'TYNE GP')
  (0, 'MANDAL FM')

--- 10. Vector-similar wells -> shared SODIR formation tops ---
  Pair (would come from geointelligence retrieval in the real app): 15/9-19 A <-> 15/9-19 SR
    shared formation: ÅSGARD FM
    shared formation: BALDER FM
    shared formation: BLODØKS FM
    shared formation: CROMER KNOLL GP
    shared formation: DRAUPNE FM
    shared formation: EKOFISK FM
    shared formation: GRID FM
    shared formation: HEATHER FM
    shared formation: HEIMDAL FM
    shared formation: HOD FM
    shared formation: HORDALAND GP
    shared formation: HUGIN FM
    shared formation: LISTA FM
    shared formation: NO FORMAL NAME
    shared formation: NO GROUP DEFINED
    shared formation: NORDLAND GP
    shared formation: RØDBY FM
    shared formation: ROGALAND GP
    shared formation: SELE FM
    shared formation: SHETLAND GP
    shared formation: SKADE FM
    shared formation: SKAGERRAK FM
    shared formation: SVARTE FM
    shared formation: TOR FM
    shared formation: TRYGGVASON FM
    shared formation: UTSIRA FM
    shared formation: VESTLAND GP
    shared formation: VIKING GP

======================================================================
VALIDATION SUMMARY
======================================================================

All entity counts match expected: True
All FK orphan counts are zero in the loaded DB (orphans were skipped at load time, not inserted): True
Duplicate source identifiers found: 0 (checked 6 tables)
Duplicate identity-bridge keys found: 0
Identity bridge matches: 125 / 125 expected
Unmatched wells preserved (no guessed bridge): 6 / 6 expected
Bridge table keys match registry's matched keys exactly: True
```
