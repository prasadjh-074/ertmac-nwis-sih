# Nearby Well Intelligence

Status: implemented and tested. Adds geographic proximity search,
combined nearby+similar well retrieval, current well state resolution,
and a FastAPI backend to the existing geological intelligence system.

## Architecture

```
graph.well_identity_link + core.wellbore (SODIR)
    ↓ (lat/lon coordinates)
nearby/
    ├── models.py       — WellLocation, NearbyWellResult, CombinedNearbyResult,
    │                     CurrentWellState
    ├── search.py       — Haversine distance, find_nearby_wells,
    │                     find_nearby_wells_by_coordinates, get_well_location
    ├── combined.py     — find_nearby_and_similar: geographic + geological
    │                     similarity with transparent component scores
    └── current_well.py — resolve_current_well, create_simulated_well

api/
    ├── schemas.py      — Pydantic response models
    └── app.py          — FastAPI application
```

## Distance Calculation

Haversine formula (great-circle distance), computed in Python. Accurate
to <0.5% for inter-well distances on the Norwegian Continental Shelf.
No PostGIS dependency.

```python
from nearby.search import haversine_km
d = haversine_km(lat1, lon1, lat2, lon2)  # returns km
```

## Well Location Model

`WellLocation` joins `graph.well_identity_link` (the FORCE/Volve ↔ SODIR
identity bridge) with `core.wellbore` to resolve:

- latitude / longitude (from `core.wellbore`)
- SODIR wellbore identity (wellbore_id, wellbore_name)
- field (from `core.field`)
- discovery (from `core.discovery`)

Wells without a SODIR link (5 of 128 embedding wells) return `None`
from `get_well_location()`. Coordinates are **never fabricated** — the
`has_coordinates` property makes missing data explicit.

## Nearby Well Search

```python
from nearby.search import find_nearby_wells

# By well ID (looks up coordinates via identity bridge)
results = find_nearby_wells("15/9-F-1", "VOLVE", radius_km=50.0, limit=10)

# By raw coordinates
from nearby.search import find_nearby_wells_by_coordinates
results = find_nearby_wells_by_coordinates(
    latitude=58.44, longitude=1.89,
    radius_km=50.0, limit=10,
    dataset_filter="VOLVE",
)
```

Supports:
- Radius filtering (only wells within `radius_km`)
- Nearest-N (`limit`)
- Deterministic ordering (distance ascending, ties broken by dataset then well_id)
- Dataset filtering (`dataset_filter`)
- Self-exclusion (the reference well is never in its own results)
- Missing-coordinate handling (wells without coords are silently excluded)

Returns `NearbyWellResult` with: well_id, dataset, latitude, longitude,
distance_km, sodir_wellbore_id, field_name, discovery_name, rank.

## Combined Nearby + Similar

```python
from nearby.combined import find_nearby_and_similar

results = find_nearby_and_similar(
    "15/9-F-1", "VOLVE",
    radius_km=50.0, limit=10,
)

for r in results:
    print(f"{r.well_id}: distance={r.distance_km}km, similarity={r.similarity}")
    print(f"  combined_relevance={r.combined_relevance}")
    print(f"  weights: distance={r.distance_weight}, similarity={r.similarity_weight}")
```

**No opaque score.** Both metrics are always exposed independently:

- `distance_km` — geographic distance (Haversine)
- `similarity` — geological similarity from the existing 30-dim
  embedding engine (`retrieval/`)

An optional `combined_relevance` score is computed transparently:

```
distance_score = max(0, 1 - distance_km / radius_km)
combined_relevance = distance_weight × distance_score + similarity_weight × similarity
```

Default weights: distance 0.4, similarity 0.6. Both weights are
returned in the result so the formula is fully reproducible.

Wells that have no embedding (and thus no similarity) have
`similarity=None` and `combined_relevance=None`.

## Current Well State

```python
from nearby.current_well import resolve_current_well, create_simulated_well

# From real database records
state = resolve_current_well("15/9-F-1", "VOLVE")
# state.is_simulated == False

# Simulated for demo purposes
sim = create_simulated_well(
    "SIM-1", "DEMO",
    latitude=60.0, longitude=3.0,
    current_depth_m=2500.0,
    current_formation="Utsira",
    drilling_parameters={"wob_kN": 120, "rpm": 60},
)
# sim.is_simulated == True — consumers must check this flag
```

Missing fields remain `None` — never fabricated. The `is_simulated`
flag clearly distinguishes synthetic demo data from real observations.

## API Endpoints

Start the server:

```bash
cd /path/to/sih
source venv/bin/activate
uvicorn api.app:app --reload --port 8000
```

| Endpoint | Description |
|----------|-------------|
| `GET /health` | Health check (DB connectivity) |
| `GET /wells?dataset=VOLVE&limit=50` | List wells with location data |
| `GET /wells/lookup?dataset=VOLVE&well_id=15/9-F-1` | Single well location + SODIR identity |
| `GET /wells/nearby?dataset=VOLVE&well_id=15/9-F-1&radius_km=50&limit=10` | Nearby wells by distance |
| `GET /wells/similar?dataset=VOLVE&well_id=15/9-F-1&top_k=10` | Similar wells by geological embedding |
| `GET /wells/context?dataset=VOLVE&well_id=15/9-F-1` | Combined: location + nearby + similar |
| `GET /wells/state?dataset=VOLVE&well_id=15/9-F-1` | Current well state |

All endpoints use query parameters for well identification (well IDs
contain `/` characters that conflict with path-based routing). All
responses use Pydantic models. All SQL is parameterized.

Interactive API docs are at `http://localhost:8000/docs` when the
server is running.

## Handling of Missing Coordinates

- `get_well_location()` returns `None` if the well has no SODIR link
  (5 of 128 embedding wells: 16/11-1S T3, 30/3-5S, 34/10-16R, 34/6-1,
  34/8-7R)
- `find_nearby_wells()` raises `ValueError` if the reference well has
  no coordinates
- Candidate wells without coordinates are silently excluded from
  nearby search results
- `WellLocation.has_coordinates` makes the missing-data case explicit
- `CurrentWellState` fields default to `None` — never fabricated

## How Nearby Wells Interact with Existing Similarity Retrieval

The nearby-well system and the existing geological similarity engine
(`retrieval/`) are **complementary, not competing**:

| | Nearby wells (`nearby/`) | Similar wells (`retrieval/`) |
|---|---|---|
| What it measures | Geographic distance (km) | Geological similarity (cosine, 30-dim embeddings) |
| Data source | `core.wellbore` coordinates via SODIR | `geointelligence.well_embeddings` |
| Works without | Embeddings | Coordinates |
| Ordering | Distance ascending | Similarity descending |

`find_nearby_and_similar()` joins both: for each geographically nearby
well, it looks up the geological similarity. The two scores are never
mixed into a single opaque number — both are always available, and the
optional `combined_relevance` shows its weights.

## Database Changes

None. This phase uses only existing tables:

- `graph.well_identity_link` (identity bridge, loaded by `load_sodir_knowledge_graph.py`)
- `core.wellbore` (SODIR wellbore with lat/lon)
- `core.field`, `core.discovery` (SODIR relational metadata)
- `geointelligence.well_embeddings` (existing 30-dim embeddings, via `retrieval/`)

## Tests

- `tests/test_nearby.py` — 48 tests total:
  - **Haversine unit tests** (7): same point, known distances, symmetry,
    equator, negative coords, antipodal
  - **Model tests** (8): WellLocation, NearbyWellResult, CurrentWellState
  - **Radius filtering** (3): correct filtering, large radius, zero radius
  - **Nearest-N** (2): limit caps, limit=1 returns closest
  - **Deterministic ordering** (3): ascending distance, sequential ranks,
    tie-breaking by dataset+well_id
  - **Missing coordinates** (1): wells without coords excluded
  - **Dataset filtering** (1): filter passed through to DB
  - **Duplicate wells** (1): self-exclusion via exclude_well
  - **Combined model** (2): with and without similarity
  - **Integration** (9): real DB — get_well_location, find_nearby,
    by_coordinates, dataset_filter, not_found, combined, current_well
  - **API integration** (11): health, list, lookup, not_found, nearby,
    similar, context, state, dataset filter

## Known Limitations

- Location data requires a SODIR link via `graph.well_identity_link` —
  5 of 128 embedding wells have no link and thus no coordinates
- Distance is Haversine (great-circle), not accounting for terrain —
  accurate to <0.5% on the NCS where wells are offshore
- `find_nearby_wells` fetches all linked wells and filters in Python
  (125 rows) rather than using a spatial index — adequate for this
  project's scale, would need PostGIS for thousands of candidates
- `CurrentWellState.current_depth_m` falls back to `total_depth_m`
  from SODIR — real-time telemetry is not yet available
- The API does not yet have authentication or rate limiting
