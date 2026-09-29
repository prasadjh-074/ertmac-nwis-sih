# Structured Query Contract

Status: this is the contract only. No Gemini/LLM integration, no LangGraph,
no database execution, and no frontend/backend exist yet. This document
and the `query/` package define what a validated query *looks like* so
that a future LLM's output has something deterministic to be checked
against before anything downstream ever executes.

## Why this exists

An LLM will eventually take a natural-language question and produce JSON.
That JSON is untrusted input. Rather than let an LLM (now or later) emit
SQL, table names, or arbitrary parameters directly, it must produce JSON
that validates against `query.StructuredQuery` - a small, closed,
enum-and-range-constrained Pydantic model. A later resolver layer (not
built here) turns a *validated* `StructuredQuery` into actual calls into
the retrieval library (`retrieval/`) and the SODIR graph
(`core.*`/`subsurface.*`/`graph.*`) - but that resolver, Gemini, and
LangGraph are all explicitly out of scope for this step.

## The six intents

| Intent | What it asks for | Backed by (already built) |
|---|---|---|
| `similar_wells` | wells similar to a target well | `retrieval.hybrid_well_search` / `search_similar_wells_by_id` |
| `similar_windows` | intervals similar to a target window | `retrieval.hybrid_window_search` / `search_similar_windows_by_id` |
| `well_information` | facts about one well | SODIR graph: `core.wellbore` + field/discovery/licence/company |
| `formation_information` | formations a well encountered | SODIR graph: `subsurface.formation_top` + `subsurface.formation` |
| `compare_wells` | two wells side by side | SODIR graph, joined for two wells |
| `geological_context` | broader graph context for a well | SODIR graph, any combination of entities |

## Fields

| Field | Type | Notes |
|---|---|---|
| `intent` | `QueryIntent` enum | required, always |
| `target_dataset` | `DatasetEnum` (`FORCE_2020` \| `VOLVE`) | the target well/window's dataset |
| `target_well_id` | `str`, pattern-constrained, max 100 chars | the target well |
| `target_window_id` | `int`, `>= 0` | the target window (only for `similar_windows`) |
| `top_k` | `int`, `1..50` | result count cap - only for the two similarity intents |
| `dataset_filter` | `DatasetEnum` | restrict similarity results to one dataset (example E) |
| `min_curves_present` | `int`, `0..11` | matches the 11 shared curves in the frozen core embedding; only for `similar_windows` |
| `comparison_dataset` / `comparison_well_id` | same shape as the target fields | **added beyond the literal brief** - `compare_wells` cannot be expressed with only one well reference, so a second well pair was the minimum addition needed to make that intent expressible at all |
| `requested_geological_context` | `List[GeologicalContextField]` enum | which SODIR graph entities to include (mirrors the entities in `docs/sodir_knowledge_graph_design.md` - `field`, `discovery`, `company`, `licence`, `formations`, `stratigraphy`, `well_history`, `casing`, `dst`, `mud`, `core`, `cuttings`, `logs`) |
| `requested_output_fields` | `List[OutputField]` enum | a curated, semantic result vocabulary (`similarity`, `depth_range`, `well_name`, `field_name`, `formations`, ...) - deliberately **not** column or table names |

Unknown/extra fields are rejected outright (`model_config = ConfigDict(extra="forbid")`).

## Hard constraints, and how they're enforced

- **No raw SQL, ever.** There is no string field wide enough to hold a
  query; every field is an enum, a bounded number, or a pattern-constrained
  identifier.
- **No table names.** `requested_geological_context` and
  `requested_output_fields` use semantic labels chosen to be independent of
  how any table is actually named - a resolver maps them internally.
- **No arbitrary executable code.** `extra="forbid"` means an LLM cannot
  smuggle an extra field (a script, a command, a second query) alongside a
  valid one. A regression test
  (`test_schema_has_no_sql_or_table_name_fields`) asserts no future field
  name can look like an SQL/exec escape hatch either.
- **Enums and ranges are validated by Pydantic itself** - `intent`,
  `target_dataset`, `dataset_filter`, `comparison_dataset`,
  `requested_geological_context` items, and `requested_output_fields`
  items are all closed enums; `top_k`, `min_curves_present`, and
  `target_window_id` all have explicit numeric bounds.
- **Optional fields are explicit** - every field defaults to `None` and is
  typed `Optional[...]`; nothing is implicitly required by omission.
- **Contradictory combinations are rejected** by a per-intent
  required/optional/forbidden table (`query/schema.py`,
  `_REQUIRED_FIELDS`/`_OPTIONAL_FIELDS`): e.g. `top_k` on `well_information`
  is rejected, `target_window_id` on `similar_wells` is rejected, and
  `compare_wells` rejects comparing a well to itself.
- **Well identifiers are pattern-constrained**
  (`^[A-Za-z0-9/\-_. ]+$`, matching every real well name seen in this
  project, e.g. `15/9-F-1`, `15/9-13 Sleipner East Appr`) - a cheap,
  explicit defense-in-depth check against SQL-injection-shaped input,
  independent of whatever parameterization a resolver would use later.

## Worked examples

### A. "Find wells similar to 15/9-F-1"
```json
{
  "intent": "similar_wells",
  "target_dataset": "VOLVE",
  "target_well_id": "15/9-F-1",
  "top_k": 10
}
```

### B. "Find intervals similar to this FORCE window"
(resolved from conversation context to a concrete window)
```json
{
  "intent": "similar_windows",
  "target_dataset": "FORCE_2020",
  "target_well_id": "15/9-13 Sleipner East Appr",
  "target_window_id": 24,
  "top_k": 5,
  "min_curves_present": 6
}
```

### C. "What formations does this well encounter?"
```json
{
  "intent": "formation_information",
  "target_dataset": "VOLVE",
  "target_well_id": "15/9-F-1",
  "requested_geological_context": ["formations", "stratigraphy"],
  "requested_output_fields": ["formations", "stratigraphic_units", "depth_range"]
}
```

### D. "Compare these two wells"
(resolved from context to two concrete wells)
```json
{
  "intent": "compare_wells",
  "target_dataset": "VOLVE",
  "target_well_id": "15/9-19 A",
  "comparison_dataset": "VOLVE",
  "comparison_well_id": "15/9-19 SR",
  "requested_geological_context": ["formations", "field"],
  "requested_output_fields": ["formations", "field_name"]
}
```

### E. "Find similar Volve wells and show their formations"
(the implicit reference well is resolved from context - here, a FORCE
well from earlier in the conversation - and `dataset_filter` restricts
the *results* to Volve; `requested_geological_context` is what makes
"show their formations" possible on a similarity intent)
```json
{
  "intent": "similar_wells",
  "target_dataset": "FORCE_2020",
  "target_well_id": "15/9-13 Sleipner East Appr",
  "dataset_filter": "VOLVE",
  "top_k": 5,
  "requested_geological_context": ["formations"],
  "requested_output_fields": ["formations", "similarity"]
}
```

All five validate successfully against `query.validate_query` (see
`tests/test_query_contract.py::test_worked_examples_are_valid`). Note that
resolving "this window" / "these two wells" / an implicit target well from
prior conversation turns is the future LLM layer's job - this contract
only represents the *already-resolved* structured form.

## What's explicitly deferred

- Gemini / any LLM integration (nothing here calls a model)
- LangGraph / any agentic orchestration
- A resolver that turns a validated `StructuredQuery` into real
  `retrieval.*` calls or SQL against `core.*`/`subsurface.*`
- Frontend/backend of any kind

## Package layout

```
query/
├── __init__.py    - public exports
├── schema.py       - StructuredQuery, enums, per-intent validation rules
└── validator.py    - validate_query / is_valid / describe_errors / validate_batch
```
