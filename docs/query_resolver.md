# Query Resolver

Status: implemented and tested. Deterministic resolution of all 6
StructuredQuery intents against the retrieval library and SODIR
relational data. No LLM, no generated SQL.

## Architecture

```
Natural Language
    ↓
GroqInterpreter (llm/)
    ↓
Validated StructuredQuery (query/)
    ↓
QueryResolver (resolver/)
    ├── retrieval/  (pgvector cosine similarity)
    ├── core.*      (SODIR wellbore, field, discovery, company, licence)
    ├── subsurface.*(formation, casing, DST, mud, core, cuttings, logs)
    └── graph.*     (FORCE/Volve ↔ SODIR identity bridge)
    ↓
ResolutionResult
```

## Intent → Data Source Mapping

| Intent | Primary Source | Secondary Source |
|---|---|---|
| `similar_wells` | `retrieval.search_similar_wells_by_id` | SODIR (if `requested_geological_context`) |
| `similar_windows` | `retrieval.search_similar_windows_by_id` | — |
| `well_information` | `graph.well_identity_link` → `core.wellbore` + joins | SODIR field/discovery/licence/company |
| `formation_information` | `subsurface.formation_top` + `subsurface.formation` | — |
| `compare_wells` | `core.wellbore` for both wells | `geointelligence.well_embeddings` for similarity |
| `geological_context` | All requested SODIR entity tables | — |

## StructuredQuery → Resolver Operation

### similar_wells

```
target_dataset + target_well_id → fetch_well_vector → search_similar_wells
    top_k → LIMIT
    dataset_filter → WHERE dataset = ...
    Self-exclusion: query well never appears in results
```

### similar_windows

```
target_dataset + target_well_id + target_window_id → fetch_window_vector → search_similar_windows
    top_k → LIMIT
    dataset_filter → WHERE dataset = ...
    min_curves_present → WHERE curves_present >= ...
    Self-exclusion: query window never appears in results
```

### well_information

```
(dataset, well_id) → graph.well_identity_link → wellbore_id
    → core.wellbore (type, purpose, status, operator, depths, dates)
    → core.field (field_name)
    → core.discovery (discovery_name)
    → core.production_licence (licence_name)
    → core.wellbore_company + core.company (company roles)
If no SODIR link exists: status = "partial", returns dataset/well_id only
```

### formation_information

```
(dataset, well_id) → graph.well_identity_link → wellbore_id
    → subsurface.formation_top (ordered by top_depth_m)
    → subsurface.formation (formation_name, stratigraphic_age)
    → parent formation (via parent_formation_id)
If no SODIR link: status = "not_found"
```

### compare_wells

```
Resolve both wells via well_information
Compute cosine similarity between their well embeddings (if both exist)
Return side-by-side structured comparison
```

### geological_context

```
(dataset, well_id) → graph.well_identity_link → wellbore_id
For each requested context field:
    field → core.field
    discovery → core.discovery
    company → core.wellbore_company + core.company
    licence → core.production_licence
    formations → subsurface.formation_top + subsurface.formation
    stratigraphy → distinct formations with hierarchy
    well_history → subsurface.wellbore_history
    casing → subsurface.casing
    dst → subsurface.dst
    mud → subsurface.mud
    core → subsurface.core
    cuttings → subsurface.cuttings
    logs → subsurface.log_curve
If no requested fields: defaults to field, discovery, company, licence, formations
```

## Result Structure

```python
ResolutionResult(
    intent="similar_wells",       # which intent was resolved
    status="success",             # "success", "partial", or "not_found"
    query={...},                  # original StructuredQuery as dict
    results=[...],                # typed results (shape depends on intent)
    result_count=10,              # number of results
    sources=["VOLVE", "SODIR"],   # provenance: which data sources contributed
    metadata={                    # intent-specific metadata
        "query_well": {"dataset": "VOLVE", "well_id": "15/9-F-1"},
    },
)
```

## Provenance

Every result preserves its source:
- **FORCE_2020** / **VOLVE**: from the embedding/retrieval layer
- **SODIR**: from the relational knowledge graph (core/subsurface schemas)

The `sources` field on `ResolutionResult` lists all data sources that
contributed to the result. Individual records carry their own
`dataset` or `source_system` field.

## Error Handling

| Error | When |
|---|---|
| `EntityNotFoundError` | Target well/window not found in embeddings or identity bridge |
| `UnsupportedIntentError` | Intent not recognized (should not happen with validated StructuredQuery) |
| `ResolverDataError` | Database connection or query failure |
| `QueryResolutionError` | Base class for all resolver errors |

Wells with no SODIR link return `status="partial"` (well_information)
or `status="not_found"` (formation_information, geological_context)
rather than raising an error — missing links are expected for some wells.

## Usage

```python
from query import validate_query
from resolver import QueryResolver

with QueryResolver() as resolver:
    q = validate_query({
        "intent": "similar_wells",
        "target_dataset": "VOLVE",
        "target_well_id": "15/9-F-1",
        "top_k": 5,
    })
    result = resolver.resolve(q)
    print(result.result_count, "similar wells found")
    for r in result.results:
        print(f"  {r['well_id']} ({r['dataset']}) similarity={r['similarity']:.3f}")
```

## Testing

```bash
# Mocked unit tests (no database needed)
pytest tests/test_resolver.py -v -m "not integration"

# Integration tests (require local PostgreSQL)
pytest tests/test_resolver.py -v -m integration

# Full suite
pytest tests/ -v -m "not live"   # 114 tests
```

## Package Layout

```
resolver/
├── __init__.py    — public exports
├── errors.py      — QueryResolutionError, EntityNotFoundError, etc.
├── models.py      — Pydantic result models (WellMatch, WindowMatch, WellInfo, etc.)
└── resolver.py    — QueryResolver with all 6 intent handlers
```

## What's Explicitly Deferred

- LangGraph or any agentic orchestration
- LLM-generated SQL or LLM in the resolver
- Frontend/backend of any kind
- Caching infrastructure
- Natural-language response generation from results
