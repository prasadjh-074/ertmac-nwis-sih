# Evaluation and Golden-Query Framework

Status: implemented and tested. Provides structured and end-to-end
evaluation of the geological intelligence query system against a curated
set of 29 golden queries covering all 6 intents, cross-dataset cases,
edge cases, and validation failures.

## Architecture

```
data/evaluation/golden_queries.json   — 29 golden queries with expected outcomes
    ↓
evaluation/loader.py                  — loads, validates, and filters queries
    ↓
evaluation/runner.py                  — structured + NL evaluation runners
    ├── run_structured_evaluation()   — no Groq needed, bypasses LLM
    └── run_nl_evaluation()           — uses GroqInterpreter, needs GROQ_API_KEY
    ↓
evaluation/metrics.py                 — 9 metric computations
    ↓
EvaluationReport                      — JSON + Markdown output
```

## Golden Query Dataset

`data/evaluation/golden_queries.json` contains 29 queries:

| Intent | Count | Tags |
|--------|-------|------|
| similar_wells | 5 | volve, force, cross-dataset, edge-case, small-pool |
| similar_windows | 3 | volve, force, edge-case |
| well_information | 4 | volve, force, sodir, edge-case, known-limitation |
| formation_information | 4 | volve, force, sodir, edge-case |
| compare_wells | 3 | volve, cross-dataset, edge-case |
| geological_context | 4 | volve, force, sodir, edge-case, multi-context |
| invalid (validation) | 4 | validation, edge-case |
| NL-only | 2 | nl-only, known-limitation |

Each query specifies:
- `structured_query`: the exact StructuredQuery dict
- `expected`: expected intent, status, result count range, sources,
  confidence label
- `natural_language` (optional): the NL question for end-to-end evaluation
- `nl_expected_override` (optional): NL-specific expectations that differ
  from structured evaluation (e.g. known Volve ID misclassification)

### Cross-dataset coverage

- Volve → FORCE similarity search (sw-03)
- Volve vs FORCE comparison (cw-02)
- Wells with and without SODIR links in both datasets

### Edge cases

- Nonexistent well IDs (sw-04, swin-03)
- Nonexistent window IDs (swin-03)
- Wells without SODIR links (wi-04, gc-03)
- Wells with 0 formation tops (fi-04)
- Compare with nonexistent well (cw-03)
- Missing required fields (inv-01)
- Extra fields rejected by `extra="forbid"` (inv-02)
- Forbidden field for intent (inv-03)
- Self-comparison (inv-04)

## Metrics

| Metric | Description |
|--------|-------------|
| `intent_accuracy` | Fraction of queries where the resolved intent matches expected |
| `entity_accuracy` | Fraction where resolver status (success/not_found) matches expected |
| `result_presence` | Fraction where result count meets minimum threshold |
| `source_correctness` | Fraction where required data sources appear in provenance |
| `provenance_completeness` | Fraction where both source and confidence checks pass |
| `resolver_success_rate` | Fraction of non-limitation, non-error queries resolved successfully |
| `invalid_query_handling` | Fraction of invalid queries correctly rejected by validation |
| `confidence_accuracy` | Fraction where confidence label falls in expected range |
| `overall_pass_rate` | Fraction of all queries passing all their checks |

## Evaluation Modes

### Structured evaluation (no Groq API key needed)

Bypasses the LLM entirely. Feeds each golden query's `structured_query`
directly into `QueryGraphRunner.run_structured_query()`. Tests the full
validate → resolve → evidence → confidence → response pipeline.

```python
from evaluation import run_structured_evaluation

report = run_structured_evaluation()
print(report.pass_rate)    # 1.0
print(report.metrics)      # 9 MetricResult objects
```

### End-to-end NL evaluation (needs GROQ_API_KEY)

Feeds each query's `natural_language` string through the full pipeline
including Groq interpretation. Exposes LLM-level issues such as the
known Volve ID misclassification.

```python
from evaluation import run_nl_evaluation

report = run_nl_evaluation()
```

### Filtering

Both runners accept filters:

```python
report = run_structured_evaluation(
    intent_filter="similar_wells",
    tag_filter=["edge-case"],
    exclude_tags=["known-limitation"],
)
```

## Report Output

### JSON report

```python
from evaluation import save_report
save_report(report, Path("data/evaluation/evaluation_report.json"))
```

### Markdown report

```python
from evaluation import format_report_markdown
md = format_report_markdown(report)
```

The Markdown report includes:
- Summary (total/passed/failed/pass_rate)
- Known limitations
- Metrics table
- Failed queries with failure details
- Passed queries with latency

## Known Limitation: Volve 15/9-19 Well IDs

The LLM prompt in `llm/prompts.py` infers `target_dataset=VOLVE` only
for well IDs matching `15/9-F-*`. Volve wells with IDs like `15/9-19 SR`
or `15/9-19 A` are misclassified as `FORCE_2020` by the LLM.

This limitation:
- Does NOT affect structured evaluation (dataset is specified directly)
- DOES affect end-to-end NL evaluation (LLM assigns the wrong dataset)
- Is explicitly tagged in the golden dataset (`known-limitation`,
  `volve-id-bug`)
- Is tracked separately in the report (`known_limitation_failures`)

Queries `wi-02`, `fi-01`, `nl-edge-02` expose this limitation.

## Testing

```bash
# Unit tests (28 tests, no live services needed)
pytest tests/test_evaluation.py -v -m "not integration and not live"

# Integration tests (3 tests, real PostgreSQL)
pytest tests/test_evaluation.py -v -m integration

# Full suite
pytest tests/ -v -m "not live"
```

## Package Layout

```
evaluation/
├── __init__.py    — public exports
├── models.py      — GoldenQuery, GoldenDataset, EvaluationReport, MetricResult, etc.
├── loader.py      — load_golden_dataset(), filter_queries()
├── metrics.py     — 9 metric functions + compute_all_metrics()
└── runner.py      — run_structured_evaluation(), run_nl_evaluation(),
                     save_report(), format_report_markdown()

data/evaluation/
├── golden_queries.json      — 29 golden queries
├── evaluation_report.json   — latest structured evaluation results
└── evaluation_report.md     — latest structured evaluation report
```
