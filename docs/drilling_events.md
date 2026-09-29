# Historical Drilling Event Intelligence

Status: implemented and tested. Extracts canonical drilling events from
SODIR wellbore history narratives, stores them in PostgreSQL, and
provides depth/formation/proximity-based correlation services.

## Architecture

```
subsurface.wellbore_history (HTML drilling narratives)
    ↓ (deterministic regex/keyword extraction)
events/
    ├── models.py       — DrillingEvent, EventType (10 types), EventSeverity,
    │                     EventProvenance, CorrelatedEvent
    ├── extraction.py   — extract_events_from_text, extract_events_for_well,
    │                     extract_all_linked_well_events, clean_html
    ├── storage.py      — store_event(s), load_events_for_well, find_events_near_depth,
    │                     find_events_by_formation, delete_events_for_well
    └── correlation.py  — correlate_historical_events (combines proximity,
                          depth, formation matching)
    ↓
subsurface.drilling_event (indexed by well, type, depth, formation)
```

## Event Types

| Type | Description | Confidence | Default Severity |
|------|-------------|------------|------------------|
| `mud_loss` | Mud losses / lost circulation | 0.90 | MEDIUM |
| `stuck_pipe` | Stuck pipe / differentially stuck | 0.85–0.90 | HIGH |
| `kick` | Well control kick (not kick-off) | 0.60–0.90 | HIGH–CRITICAL |
| `overpressure` | Abnormally high pressure | 0.80–0.85 | MEDIUM–HIGH |
| `torque_spike` | High / erratic torque | 0.75–0.80 | MEDIUM |
| `cementing_issue` | Cement failure / remedial squeeze | 0.85 | MEDIUM–HIGH |
| `casing_issue` | Casing failure / leak / collapse | 0.85 | HIGH |
| `fishing` | Fishing operations / lost in hole | 0.75–0.90 | MEDIUM–HIGH |
| `npt` | Non-productive time | 0.80–0.85 | MEDIUM |
| `other` | Tight hole, hole instability, J&A | 0.70–0.90 | LOW–CRITICAL |

## Extraction Engine

Fully deterministic — no LLM, no ML model. Uses:

1. **HTML stripping** — `clean_html()` removes tags, decodes entities,
   normalizes whitespace
2. **Event-type regex patterns** — 26 patterns with per-type confidence
   and severity hints
3. **Kick/kick-off disambiguation** — excludes "kick-off" / "kicked off"
   (sidetrack operations) from well-control kick detections
4. **Depth extraction** — parses "at X m", "X–Y m" ranges, "mMD", "mTVD"
   from a ±200-char context window around each event match
5. **Formation extraction** — reuses `ingestion.nlp.entity_extractor`
   patterns (FORMATION_SUFFIX_RE and formation dictionary lookup)
6. **Severity escalation** — contextual keywords ("severe", "total loss",
   "major") can escalate the base severity
7. **Span deduplication** — overlapping matches of the same event type
   are deduplicated

```python
from events.extraction import extract_events_from_text

events = extract_events_from_text(
    text="<p>Stuck pipe at 2500 m in the Heimdal Formation</p>",
    well_id="15/9-F-1",
    dataset="VOLVE",
    sodir_wellbore_id=1234,
    source_record_id=42,
)
# events[0].event_type == EventType.STUCK_PIPE
# events[0].depth_start_m == 2500.0
# events[0].provenance.extraction_confidence == 0.90
```

### Batch Extraction

```python
from events.extraction import extract_events_for_well, extract_all_linked_well_events

# Single well
events = extract_events_for_well("15/9-F-1", "VOLVE")

# All 115 linked wells (for initial DB population)
all_events = extract_all_linked_well_events()
```

## Provenance

Every event carries full source traceability:

```python
EventProvenance(
    source_type="sodir_history",
    source_table="subsurface.wellbore_history",
    source_record_id=42,       # history_id
    extraction_method="regex_keyword",
    extraction_confidence=0.90,
    raw_text_snippet="stuck pipe at 2500 m in the Heimdal Formation",
)
```

Fields that cannot be determined remain `None` — never fabricated.
Low-confidence extractions (e.g. bare "kick" without well-control
context) carry `extraction_confidence=0.60`.

## Database Schema

Migration: `db/006_drilling_events.sql`

Table: `subsurface.drilling_event`

Indexes:
- `(well_id, dataset)` — per-well lookup
- `(event_type)` — type-based queries
- `(depth_start_m)` — depth-range queries (WHERE NOT NULL)
- `(formation)` — formation-based queries (WHERE NOT NULL)
- `(sodir_wellbore_id)` — SODIR link (WHERE NOT NULL)

## Storage API

```python
from events.storage import (
    store_event, store_events,
    load_events_for_well,
    find_events_near_depth,
    find_events_by_formation,
    delete_events_for_well,
    count_events,
)

# Store
ids = store_events(events)

# Load for well (optionally filtered by event type)
events = load_events_for_well("15/9-F-1", "VOLVE", event_type=EventType.STUCK_PIPE)

# Depth correlation: events within ±100m of target depth
nearby_events = find_events_near_depth("15/9-F-1", "VOLVE", target_depth_m=2500.0, tolerance_m=100.0)

# Formation correlation: events in a formation across all wells
formation_events = find_events_by_formation("Heimdal")
```

All SQL uses parameterized placeholders. No SQL is generated from user
input or LLM output.

## Correlation Service

`correlate_historical_events()` combines four factors to find the most
relevant historical events for a current drilling context:

1. **Own well** — events from the same well (bonus: +0.3)
2. **Nearby wells** — geographic proximity via `nearby.search.find_nearby_wells`
   (score: 0.25 × (1 - distance/radius))
3. **Depth overlap** — events within tolerance of current depth (+0.25)
4. **Formation match** — events in the same formation (+0.2)

All factor scores are multiplied by extraction confidence
(min 0.5) for a final relevance score.

```python
from events.correlation import correlate_historical_events

results = correlate_historical_events(
    well_id="15/9-F-1",
    dataset="VOLVE",
    current_depth_m=2500.0,
    current_formation="Heimdal",
    radius_km=50.0,
    depth_tolerance_m=100.0,
    limit=20,
    event_type=EventType.STUCK_PIPE,  # optional filter
)

for r in results:
    print(f"{r.event.event_type.value}: {r.event.description}")
    print(f"  well={r.source_well_id}, dist={r.distance_km}km")
    print(f"  depth_overlap={r.depth_overlap}, formation_match={r.formation_match}")
    print(f"  relevance={r.relevance_factors['score']}")
```

Each `CorrelatedEvent` exposes all correlation factors transparently —
no opaque combined score without its components.

## Data Coverage

From SODIR `wellbore_history` for 115 linked wells:
- 1979 history records (HTML drilling narratives)
- Event keyword frequencies: stuck=216, kick=372, loss=90, mud_loss=38,
  cement=287, torque=9, fishing=78, NPT=39
- 2956 formation tops for linked wells (for formation correlation)

## Tests

`tests/test_events.py` — 51 tests:

- **Model tests** (9): EventType enum, EventSeverity enum, DrillingEvent
  defaults and full construction, CorrelatedEvent creation and defaults
- **HTML cleaning** (5): tag stripping, nested tags, entities, whitespace, empty
- **Depth extraction** (5): single depth, range, multiple depths, no depth, mMD
- **Severity escalation** (4): severe, total loss, no escalation, already critical
- **Event extraction** (18): stuck pipe, mud loss, lost circulation,
  kick/kick-off disambiguation, fishing, HTML input, empty text,
  provenance fields, multiple event types, deduplication, severity
  escalation, NPT, overpressure, cementing, casing, hole instability
- **Storage (mocked)** (4): store single, store batch, store empty, count
- **Integration: extraction** (2): extract for known well, nonexistent well
- **Integration: storage** (3): store/load/delete round-trip,
  find_events_near_depth, find_events_by_formation
- **Integration: correlation** (2): correlate returns list, nonexistent well

## How This Integrates with Phase 1

The correlation service uses Phase 1's `find_nearby_wells()` to find
geographically proximate wells, then loads their stored events.
This creates a chain:

```
Current well context (depth, formation)
    → nearby/search.py (Haversine proximity)
    → events/storage.py (load events for nearby wells)
    → events/correlation.py (rank by depth/formation/distance)
    → List[CorrelatedEvent] (scored, sorted, fully traceable)
```

## Known Limitations

- Event extraction is regex/keyword-based — complex narrative context
  (negation, hypotheticals) may produce false positives at lower
  confidence levels
- Kick/kick-off disambiguation uses a ±30-char window around the match;
  edge cases exist where "kick" appears far from "off"
- Formation extraction depends on the ingestion ontology dictionary —
  formations not in `ontology/aliases.yaml` won't be recognized
- Depth extraction requires explicit units (m, meters, mMD, mTVD) —
  bare numbers without units are ignored
- The correlation service does not yet incorporate geological similarity
  (embeddings) — it uses geographic proximity from Phase 1 only
