# Query-Time LangGraph Orchestration

Status: implemented and tested. Wires the existing `GroqInterpreter`,
`StructuredQuery` contract, and `QueryResolver` into one deterministic
LangGraph `StateGraph`. No component's logic is duplicated - this layer
only sequences existing calls and adds a confidence heuristic plus a
template-based final answer.

## Architecture

```
User question
    ↓
GroqInterpreter (llm/)          — unchanged, reused as-is
    ↓
StructuredQuery (query/)        — unchanged, reused as-is
    ↓
LangGraph (graph/)
    ├── interpret               — calls GroqInterpreter.interpret()
    ├── validate                — calls query.validate_query()
    ├── resolve                 — calls QueryResolver.resolve()
    ├── collect_evidence        — normalizes ResolutionResult -> EvidenceItem[]
    ├── retrieve_documents      — document chunk search (see docs/document_retrieval.md)
    ├── fuse_evidence           — deduplication, grouping, provenance, conflicts
    ├── calculate_confidence    — deterministic heuristic (see below)
    └── generate_response       — template-based answer, no LLM
    ↓
QueryResponse
```

Document retrieval (`retrieve_documents`) runs between `collect_evidence`
and `fuse_evidence` for any query with `search_text` set - either the
document-only `document_search` intent, or a well/SODIR intent combined
with `search_text`. It never touches the well/window embedding space; see
[docs/document_retrieval.md](document_retrieval.md) for the full design.

## Why LangGraph

- **Orchestration**: six fixed stages need one explicit place that
  sequences them, instead of a chain of ad-hoc function calls scattered
  across callers.
- **Explicit state**: every intermediate artifact (structured query,
  resolution result, evidence, confidence) is a named, inspectable field
  on `GraphState` rather than a local variable buried in a call stack.
- **Controlled execution**: conditional edges make failure paths
  (invalid query, resolver error) first-class routes instead of
  exceptions that abort the whole run.
- **Future extension**: this graph is a single linear path today - no
  autonomous agents, no branching LLM decisions, no tool-calling loop.
  The same `StateGraph` scaffold is where a later stage could add a
  clarification loop or multi-step retrieval without changing
  `interpret`/`validate`/`resolve` themselves.

## Graph Flow

```
START
  ↓
interpret ──(no structured_query)──────────────► collect_evidence
  ↓ (structured_query present)
validate ──(invalid)───────────────────────────► collect_evidence
  ↓ (valid)
resolve
  ↓
collect_evidence
  ↓
calculate_confidence
  ↓
generate_response
  ↓
END
```

Both failure shortcuts route to `collect_evidence` (not directly to
`generate_response`) so that `collect_evidence` and
`calculate_confidence` always run - they handle a missing
`resolution_result` cleanly (empty evidence list; confidence fixed at
`0.0`/`"none"`), so `confidence_score` is **always** populated in the
final `QueryResponse`, never left as `None`.

## Node Reference

| Node | Calls | On failure |
|---|---|---|
| `interpret` | `GroqInterpreter.interpret()` (or pass-through if `structured_query` was pre-supplied) | Records `GraphError(stage="interpret", ...)`, routes to `collect_evidence` |
| `validate` | `query.validate_query()` | Records `GraphError(stage="validate", ...)`, clears `structured_query`, routes to `collect_evidence` — **never touches PostgreSQL or retrieval for an invalid query** |
| `resolve` | `QueryResolver.resolve()` | Records `GraphError(stage="resolve", ...)`, `resolution_result` stays `None` |
| `collect_evidence` | Pure function over `ResolutionResult.results` | N/A (never raises) |
| `calculate_confidence` | Pure function, deterministic heuristic | N/A (never raises) |
| `generate_response` | Pure function, template-based | N/A (never raises) |

## Evidence Collection

`collect_evidence` builds `EvidenceItem` objects from
`ResolutionResult.results`, with the mapping depending on intent:

| Intent | Evidence per | `entity_type` | `source_id` |
|---|---|---|---|
| `similar_wells` | matched well | `"well"` | — |
| `similar_windows` | matched window | `"window"` | `window_id` |
| `well_information` | the well itself | `"well_info"` | `sodir_wellbore_id` |
| `formation_information` | each formation top | `"formation"` | `formation_id` |
| `compare_wells` | target + comparison (+ similarity, if computed) | `"well_info"` / `"similarity_score"` | `sodir_wellbore_id` |
| `geological_context` | each record in each requested group | group's `entity_type` | — |

`source_system` is always read from the underlying record's own
`dataset` or `source_system` field (`FORCE_2020`, `VOLVE`, or `SODIR`) -
never guessed, never collapsed across systems. No evidence is invented:
an empty `ResolutionResult.results` produces an empty evidence list.

## Confidence Score

`confidence_score` is a **deterministic, heuristic indicator - explicitly
not a calibrated statistical probability**. It is a weighted sum of four
components, each in `[0, 1]`:

| Component | Weight | Rule |
|---|---|---|
| `status_component` | 0.40 | `1.0` if `ResolutionResult.status == "success"`, `0.5` if `"partial"`, `0.0` if `"not_found"` |
| `presence_component` | 0.30 | `1.0` if `result_count > 0`, else `0.0` |
| `similarity_component` | 0.20 | Mean similarity across result records that carry one (`similar_wells`, `similar_windows`, `compare_wells`); `0.0` if the intent has similarity but none was found; `0.5` (neutral) for intents with no similarity concept at all |
| `provenance_component` | 0.10 | `1.0` if backed by 2+ distinct source systems, `0.5` if exactly one, `0.0` if none |

```
value = 0.40·status + 0.30·presence + 0.20·similarity + 0.10·provenance
label = "high" if value >= 0.75 else "medium" if value >= 0.4 else "low"
```

If interpretation or validation failed before the resolver ever ran,
`value` is fixed at `0.0` with `label = "none"` - there is nothing to be
confident about. The `factors` dict on `ConfidenceScore` always shows
each component's value for inspection, and `note` always states the
heuristic-not-probability disclaimer.

## Final Response

`generate_response` produces a deterministic, template-based `answer`
string per intent - purely from fields already present in
`ResolutionResult`. It never asks an LLM to interpret, embellish, or draw
geological conclusions. Examples:

- `similar_wells`: `"Found 5 well(s) similar to 15/9-F-1 (VOLVE)."`
- `well_information`: `"Well 15/9-F-1 (VOLVE) is linked to SODIR wellbore 6419, field VOLVE, operated by Statoil Petroleum AS."`
- `formation_information`: `"Found 31 formation top(s) for the requested well."`
- `compare_wells`: `"Compared 15/9-F-1 (VOLVE) with 15/9-F-4 (VOLVE). Embedding cosine similarity: 0.870."`

If `status == "not_found"` or `"partial"`, a plain factual suffix is
appended (e.g. `"No SODIR-linked data was available for this well."`) -
never a speculative explanation.

## Public API

```python
from graph import QueryGraphRunner

# Full pipeline: natural language -> Groq -> ... -> QueryResponse
runner = QueryGraphRunner()
response = runner.run_query("What wells are similar to 15/9-F-1?")

# Deterministic mode: bypasses Groq entirely (for tests/demos without a
# live API key, or when the caller already has a StructuredQuery)
runner2 = QueryGraphRunner(use_llm=False)
response2 = runner2.run_structured_query({
    "intent": "similar_wells",
    "target_dataset": "VOLVE",
    "target_well_id": "15/9-F-1",
    "top_k": 5,
})

print(response.answer)
print(response.confidence_score.value, response.confidence_score.label)
print(response.provenance)          # e.g. ["FORCE_2020", "VOLVE"]
print(response.metadata.total_execution_ms)
```

### `QueryResponse` fields

```python
class QueryResponse(BaseModel):
    answer: str
    structured_query: Optional[Dict[str, Any]]
    evidence: List[EvidenceItem]
    confidence_score: Optional[ConfidenceScore]
    provenance: List[str]
    metadata: ExecutionMetadata
    errors: List[GraphError]
```

## Execution Metadata

Tracked per run, never includes API keys or credentials:

```python
class ExecutionMetadata(BaseModel):
    total_execution_ms: Optional[float]
    intent: Optional[str]
    result_count: Optional[int]
    data_sources: List[str]
    llm_used: bool
    node_status: Dict[str, str]   # e.g. {"interpret": "success", "resolve": "failed", ...}
```

## Error Handling

| Failure | Where caught | Result |
|---|---|---|
| Groq API failure / bad JSON | `interpret` node | `GraphError(stage="interpret")`, graph completes with `answer` describing the failure |
| Invalid `StructuredQuery` | `validate` node | `GraphError(stage="validate")`, resolver never called |
| Resolver error (unknown well, DB error) | `resolve` node | `GraphError(stage="resolve")`, `resolution_result=None` |
| No results | `resolve` node (not an error) | `result_count=0`, low confidence, factual answer |

The graph never raises an uncaught exception for any of the above - it
always returns a `QueryResponse` with `errors` populated instead. The
only exception type the graph package defines for itself,
`GraphExecutionError`, is reserved for genuinely unanticipated failures
and is not raised by any node in normal operation.

## Testing

```bash
# Unit tests (mocked Groq + mocked resolver, no live services needed)
pytest tests/test_query_graph.py -v -m "not live and not integration"

# Integration tests (real PostgreSQL, Groq boundary still mocked)
pytest tests/test_query_graph.py -v -m integration

# Full suite
pytest tests/ -v -m "not live"   # 134 tests
```

## Package Layout

```
graph/
├── __init__.py    — public exports
├── errors.py      — GraphError, GraphExecutionError
├── state.py       — GraphState (TypedDict), EvidenceItem, ConfidenceScore,
│                    ExecutionMetadata, QueryResponse
├── nodes.py        — the 6 node implementations + routing functions
└── workflow.py    — StateGraph wiring + QueryGraphRunner
```

## What's Explicitly Deferred

- Autonomous or multi-agent behavior (this is a single linear path)
- LLM-generated SQL, or an LLM anywhere downstream of `interpret`
- Frontend / REST API
- Caching or persistence (no LangGraph checkpointer is configured)
- Natural-language response generation beyond fixed templates

## Known Limitation

The system prompt in `llm/prompts.py` (built in the prior stage, reused
here unmodified) infers `target_dataset=VOLVE` only for well IDs matching
`15/9-F-*`. Volve wells outside that pattern (e.g. `15/9-19 SR`,
`15/9-19 A`) can be misclassified as `FORCE_2020` by the LLM when the
question doesn't state the dataset explicitly. When this happens, the
graph does not crash or fabricate data: `resolve` returns
`status="not_found"`, confidence drops accordingly, and the answer states
plainly that no SODIR-linked data was available. Fixing this is a prompt
change in `llm/prompts.py`, outside this stage's scope.
