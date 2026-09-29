# Explainability and Evidence Fusion

## Overview

The geological intelligence system provides deterministic explainability for every query response. No LLM is used for evidence fusion, rationale generation, or confidence explanation — all logic is rule-based and reproducible.

Every response answers three questions:
1. **What** was found (the answer)
2. **Why** this answer was produced (rationale)
3. **How confident** the system is, and on what basis (confidence + basis)

## Architecture

```
StructuredQuery
    → validate → resolve → collect_evidence
    → fuse_evidence → calculate_confidence → generate_response
```

The `fuse_evidence` node sits between evidence collection and confidence calculation. It deduplicates, groups, detects conflicts, and tracks missing information — all deterministically.

## Evidence Package

### `evidence/models.py`

Typed models for the evidence layer:

- **ProvenanceRecord** — tracks where each evidence item came from (source system, retrieval mechanism, entity type)
- **FusedEvidenceItem** — enriched evidence item with provenance, explanation, and relevance
- **SourceDifference** — represents a conflict between two sources for the same field (e.g., different operators in FORCE vs SODIR)
- **MissingInfo** — explicitly represents what was *not* found and why (`not_found`, `not_linked`, `not_available`, `not_resolved`)
- **EvidenceGroup** — groups evidence items by entity type
- **FusedEvidence** — the complete fusion result: items, groups, differences, missing info, source systems

### `evidence/fusion.py`

Deterministic fusion pipeline:

1. **Build fused items** — converts raw `EvidenceItem` objects to `FusedEvidenceItem` with provenance and explanation
2. **Deduplicate** — removes duplicates by `(source_system, entity_type, well_id, source_id, similarity)` key
3. **Group by entity** — organizes items by entity type (well, formation, field, company, etc.)
4. **Detect differences** — finds conflicting values across sources for the same well and field
5. **Detect missing info** — identifies gaps: no results found, partial data, no SODIR link, no formations

### `evidence/provenance.py`

Maps each evidence item to its retrieval mechanism:
- `vector_similarity` — for well and window entities (pgvector cosine distance)
- `sodir_relational` — for formation, field, company, and other SODIR entities
- `identity_link` — for well identity bridge lookups

### `evidence/rationale.py`

Generates human-readable rationale per intent:

| Intent | Rationale Template |
|--------|-------------------|
| `similar_wells` | "Matched using cosine similarity between the query well embedding and candidate well embeddings." |
| `similar_windows` | "Matched using cosine similarity between the query depth-window embedding and candidate window embeddings." |
| `well_information` | "Information retrieved from the SODIR wellbore and related entities via the identity link." |
| `formation_information` | "Formation tops retrieved from SODIR formation_top records linked to the wellbore." |
| `compare_wells` | "Side-by-side comparison of two wells using SODIR metadata and embedding cosine similarity." |
| `geological_context` | "Context combines SODIR relational evidence with available well/retrieval evidence." |

Each rationale also includes:
- Evidence count and type breakdown (vector vs SODIR)
- Similarity range for vector-based results
- Provenance summary
- Source differences (if any)
- Missing information (if any)

## Confidence Explanation

The `ConfidenceScore` model includes:

```python
class ConfidenceScore(BaseModel):
    value: float          # 0.0 to 1.0
    label: str            # "none", "low", "medium", "high"
    factors: dict         # raw scoring factors
    basis: List[str]      # human-readable explanation
    is_probability: bool  # always False — this is a heuristic score
```

The `basis` field explains *why* the confidence score is what it is:
- Whether the query resolved successfully
- How many results were found
- How many source systems contributed
- Whether high-similarity evidence is available
- Whether a query was only partially resolved

`is_probability` is always `False` — the score is a deterministic heuristic, not a statistical probability.

## Source Differences

When the same well appears in multiple sources (e.g., FORCE_2020 and SODIR), the system compares field values and reports differences without resolving them:

```
Source difference: operator — FORCE_2020 says "Equinor" but SODIR says "Statoil Petroleum AS"
```

This preserves data integrity: the system never silently picks one value over another.

## Missing Information

Missing data is explicitly categorized:

| Reason | Meaning |
|--------|---------|
| `not_found` | The entity was searched for but not found in any source |
| `not_linked` | The well exists but has no SODIR identity link |
| `not_available` | The data category exists but has no records (e.g., 0 formation tops) |
| `not_resolved` | The query never reached the resolver (validation failure) |

## Evaluation Metrics

Three explainability metrics are tracked in the evaluation framework:

| Metric | What it checks |
|--------|---------------|
| `evidence_presence` | Successful queries include evidence items |
| `rationale_presence` | All non-validation-failure queries include rationale |
| `unsupported_claim_count` | Answers contain no speculative language ("probably", "likely indicates", etc.) |

## Example Output

```
ANSWER
Well 34/6-1 (FORCE_2020) has no matching SODIR record. Some information was unavailable.

WHY (rationale)
1. Information retrieved from the SODIR wellbore and related entities via the identity link.
2. 1 evidence item(s) collected.
3. SODIR relational evidence: 1 item(s).
4. Provenance from single source: FORCE_2020.
5. Missing: Some requested information was unavailable (not_linked).
6. Missing: Well has no SODIR identity link (not_linked).

EVIDENCE (1 item(s))
1. [FORCE_2020/well_info] well_id=34/6-1

PROVENANCE
['FORCE_2020']

CONFIDENCE
0.65 — medium
is_probability: False

CONFIDENCE BASIS
- query partially resolved
- 1 retrieval result(s) found
- provenance from single source (FORCE_2020)
- similarity not applicable for this intent
```

## Design Principles

1. **No LLM in the evidence layer** — all fusion, rationale, and confidence explanation is deterministic
2. **No unsupported conclusions** — the system reports data, not geological interpretations
3. **Source preservation** — FORCE_2020, VOLVE, and SODIR are kept distinct; conflicts are reported, not resolved
4. **Explicit gaps** — missing information is categorized and surfaced, never silently omitted
5. **Reproducibility** — the same query always produces the same rationale and basis
