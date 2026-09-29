# Risk Intelligence & Alert Engine

Phase 3 of eRTMAC-NWIS: evidence-based drilling risk assessment and alert
generation from historical events, DST pressure, mud weight, and caliper data.

## Design Decision: Evidence-Based, Not ML

Data availability assessment (2026-09-28):

| Event type       | Count | Wells |
|-----------------|-------|-------|
| mud_loss        | 10    | 9     |
| stuck_pipe      | 8     | 7     |
| overpressure    | 5     | 5     |
| formation_damage| 4     | 4     |
| kick            | 0     | 0     |
| torque_spike    | 0     | 0     |
| cementing_issue | 0     | 0     |

**Total: 31 events across 20 wells.**  Minimum ~30-50 positive examples per
class with well-level separation is needed for any model-based approach.
All five risk types use deterministic, evidence-based scoring.

## Risk Types

| Risk Type | Mapped Event Types | Supplementary Data |
|-----------|-------------------|-------------------|
| `mud_loss_risk` | MUD_LOSS | mud weight |
| `stuck_pipe_risk` | STUCK_PIPE | caliper washout, mud weight |
| `kick_overpressure_risk` | KICK, OVERPRESSURE | DST pressure (BHP), mud weight |
| `torque_spike_risk` | TORQUE_SPIKE | — |
| `cementing_risk` | CEMENTING_ISSUE | caliper washout |

## Scoring Engine (`risk/scoring.py`)

Each risk type gets a composite score built from transparent, weighted
components:

### Without supplementary evidence
| Component | Weight | Source |
|-----------|--------|--------|
| Frequency | 0.30 | event count / 10, capped at 1.0 |
| Proximity | 0.25 | 1 − (distance_km / 50), avg over events |
| Depth overlap | 0.20 | fraction of events overlapping current depth |
| Formation match | 0.15 | fraction of events matching current formation |
| Severity | 0.10 | weighted average of event severities |

### With supplementary evidence (DST/mud/caliper)
| Component | Weight |
|-----------|--------|
| Frequency | 0.25 |
| Proximity | 0.20 |
| Depth overlap | 0.15 |
| Formation match | 0.10 |
| Severity | 0.10 |
| Supplementary | 0.20 |

**Score → Level mapping:**
- ≥ 0.6 → HIGH
- ≥ 0.3 → MEDIUM
- < 0.3 → LOW

All scores are heuristic evidence indicators, **not** calibrated probabilities.
This is stated in every RiskAssessment's `limitations` field.

## Supplementary Evidence Sources (`risk/evidence_sources.py`)

### DST Pressure (`subsurface.dst`)
- 1,187 records with shut-in, flow, and bottom-hole pressure
- Used for `kick_overpressure_risk`: high BHP signals overpressure potential
- Filtered by depth tolerance (default ±500m from target)

### Mud Weight (`subsurface.mud`)
- 36,714 records with mud weight and mud type
- Used for `kick_overpressure_risk` (elevated weight → pressure challenges),
  `mud_loss_risk` (high weight → fracture risk), `stuck_pipe_risk` (context)
- Filtered by depth tolerance (default ±300m)

### Caliper (`unified_features.parquet`)
- 19,763 windows × 113 columns across 131 wells
- Washout ratio = caliper_mean / bit_size_mean
- Used for `stuck_pipe_risk` (washout >15% → hole instability) and
  `cementing_risk` (washout >20% → complicates cement)
- Filtered by depth tolerance (default ±200m)

## Rule Engine (`risk/rules.py`)

Seven deterministic rules that fire independently of scoring:

| Rule | Trigger Condition | Severity |
|------|-------------------|----------|
| `formation_history_warning` | ≥2 events match current formation | MEDIUM/HIGH |
| `nearby_stuck_pipe_history` | nearby wells have stuck pipe (excludes own) | MEDIUM/HIGH |
| `nearby_mud_loss_history` | nearby wells have mud loss | MEDIUM/HIGH |
| `kick_history_warning` | any kick/overpressure event present | HIGH |
| `torque_history_warning` | any torque spike event | MEDIUM |
| `cementing_history_warning` | any cementing issue event | MEDIUM |
| `high_risk_event_cluster` | ≥3 high/critical events of ≥2 types | HIGH |

## Alert Generation (`risk/alerts.py`)

Alerts are generated from both risk assessments (above LOW) and triggered
rules. Each alert includes:

- **severity**: INFO / WARNING / HIGH / CRITICAL
- **evidence**: traceable list of evidence strings
- **recommended_action**: risk-type and level-specific recommendation
- **provenance**: `evidence_rule_based` or `deterministic_rule`
- **context**: well_id, dataset, score, methodology

Alerts are sorted by severity (CRITICAL first).

Recommendations are **decision support only** — the system does not claim
autonomous drilling control.

## LangGraph Integration

Two new nodes in the 10-node query pipeline:

```
interpret → validate → resolve → collect_evidence → retrieve_documents
  → fuse_evidence → assess_risk → generate_alerts → calculate_confidence
  → generate_response
```

### `assess_risk_node`
- Runs only when query has `target_well_id`
- Calls `correlate_historical_events` + `gather_well_evidence`
- Produces `risk_assessments` and `rule_results` in state

### `generate_alerts_node`
- Runs only when risk assessments or rule results exist
- Produces `alerts` in state

Both are exposed in `QueryResponse.risk_assessments` and
`QueryResponse.alerts`.

## GraphState Fields

```python
risk_assessments: Optional[List[RiskAssessment]]
rule_results: Optional[List[RuleResult]]
alerts: Optional[List[Alert]]
```

## Security

- All SQL uses parameterized placeholders (no LLM-generated SQL)
- No API keys or credentials in risk models or state
- Parquet reads are local filesystem only

## Test Coverage

71 tests in `tests/test_risk.py`:
- Model enum/dataclass tests
- Scoring: no events, single/multiple events, proximity, depth, formation,
  own-well, irrelevant types, score cap, confidence, provenance
- Supplementary: DST pressure, mud weight, caliper washout, cementing,
  empty evidence, supplementary-only
- Rules: all 7 rules trigger/no-trigger, evaluate_all, empty events
- Alerts: LOW/MEDIUM/HIGH levels, provenance, sorting, recommendations
- LangGraph nodes: skip/success, QueryResponse fields
- Missing data: empty events, no evidence, None evidence

Full suite: 484 tests passing (no regressions from 413 prior).
