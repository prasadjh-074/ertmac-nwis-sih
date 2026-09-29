# Document Retrieval (Query-Time)

Status: implemented and tested. Adds semantic search over ingested
document chunks (`ingestion/`) to the query-time LangGraph orchestration
(`graph/`), so a question can pull in document evidence alongside - or
instead of - well/SODIR evidence.

## The core rule: two vector spaces, never merged

| | Well/window embeddings (`retrieval/`) | Document chunk embeddings (`document_retrieval/`) |
|---|---|---|
| Dimensions | ~30 (frozen, leakage-reduced core embedding) | 384 (`all-MiniLM-L6-v2`, sentence-transformers) |
| Storage | `geointelligence.window_embeddings` / `well_embeddings` | `document_chunks.embedding` |
| Built by | Well-log curve statistics pipeline | `ingestion/embeddings/sentence_transformer_embedder.py` |
| Queried by | `retrieval/vector_search.py` | `document_retrieval/search.py` |

These two embedding spaces are **never compared, concatenated, or
averaged**. Every place they could plausibly meet is kept apart on
purpose:

- Separate database columns (different `vector(N)` dimension, different
  tables).
- Separate Python packages (`retrieval/` vs. `document_retrieval/`),
  each with its own connection helper and query builder.
- Separate `EvidenceItem.entity_type` values (`"well"` / `"window"` vs.
  `"document_chunk"`) and separate `source_type` labels after fusion
  (`"vector_similarity"` vs. `"document"`).
- Separate confidence factors (`similarity_component` for well/window
  similarity vs. `document_similarity_mean` / the document-only
  formula below) - a combined query's well confidence is **never**
  averaged with its document similarity.

## Architecture

```
document_chunks (ingestion/)
    ↓ (384-dim, pgvector)
document_retrieval/
    ├── models.py      — DocumentSearchResult (chunk_id, file_name, page,
    │                    section, text, similarity, rank)
    ├── filters.py      — DocumentFilters: parameterized WHERE-clause
    │                    fragments (source_type, file_name)
    ├── ranking.py       — cosine distance -> similarity, 1-indexed rank
    └── search.py        — embed_query() + search_documents(): the only
                          module that talks to PostgreSQL for documents
    ↓
graph/nodes.py::retrieve_documents_node
    ↓ (appends EvidenceItem(entity_type="document_chunk", ...))
evidence/fusion.py::fuse_evidence  — source_type="document"
    ↓
QueryResponse (evidence, provenance, confidence, rationale)
```

## StructuredQuery extension

Three new optional fields, settable on `document_search` or on any
well/SODIR intent (for a **combined** query):

| Field | Type | Notes |
|---|---|---|
| `search_text` | `str`, max 500 chars | Embedded with the same sentence-transformer model used at ingestion time. Never used to build SQL text. |
| `document_source_type` | `DocumentSourceType` enum (`pdf` / `text` / `image`) | Mirrors `ingestion/schemas.py`'s `SourceType` literal |
| `document_file_name` | `str`, bounded pattern (same charset rule as `well_id`) | Exact match on `documents.file_name` |

A new intent, `document_search`, is **document-only**:

```json
{"intent": "document_search", "search_text": "formation tops in well 30/6-1", "top_k": 5}
```

- Required: `search_text`.
- Optional: `top_k`, `document_source_type`, `document_file_name`.
- Forbidden: every well/SODIR field (`target_dataset`, `target_well_id`,
  `comparison_*`, `requested_geological_context`, ...) - enforced by the
  same `extra="forbid"` + per-intent field-applicability mechanism as
  every other intent (`query/schema.py`).

A **combined** query is any of the other six intents with `search_text`
also set:

```json
{
  "intent": "well_information",
  "target_dataset": "VOLVE", "target_well_id": "15/9-F-1",
  "search_text": "well report information"
}
```

This runs `well_information` exactly as before (unaffected resolver
path) **and** additionally attaches document evidence found for
`search_text`. No SQL is ever generated from `search_text` - it is only
ever passed to the sentence-transformer embedder and then to a
parameterized `<=>` (cosine distance) query.

## Graph integration

`retrieve_documents_node` sits between `collect_evidence` and
`fuse_evidence` (see [docs/query_graph.md](query_graph.md)):

- Skips cleanly (`node_status["retrieve_documents"] = "skipped"`) if
  `structured_query.search_text` is not set - the overwhelming majority
  of queries (all 29 original golden queries) never reach
  `document_retrieval/` at all.
- For `document_search`, `resolve` is skipped entirely
  (`node_status["resolve"] = "skipped_document_only"`) - it never touches
  the well/SODIR resolver or opens a `QueryResolver` connection.
- Appends document `EvidenceItem`s onto whatever `collect_evidence`
  already produced; it never overwrites well evidence.
- On a document-store failure (e.g. the database is unreachable), it
  records `GraphError(stage="retrieve_documents", ...)` without raising -
  the same fail-soft pattern as every other node.

## Evidence fusion

`evidence/fusion.py` and `evidence/provenance.py` add one new
`entity_type` throughout:

| `entity_type` | `source_type` | `retrieval_mechanism` |
|---|---|---|
| `"document_chunk"` | `"document"` | `"document_vector_similarity"` |

A fused document item's `explanation` names the source file and page
(`"Matched chunk in sample_well_report.txt, page 1, cosine similarity:
0.580"`). `FusedEvidenceItem.value` carries the full chunk metadata
(`file_name`, `page_number`, `chunk_index`, `section`, `text`) so the
snippet is always available without a second database round-trip.

`generate_rationale()` reports document evidence as its own line,
explicitly noting the separate 384-dim space, and `document_search` has
its own entry in the intent-rationale table.

## Confidence scoring

Two distinct paths, never blended:

1. **`document_search` (document-only)** - `result` (`ResolutionResult`)
   is always `None` by design, so `calculate_confidence_node` uses a
   document-only formula with the *same shape* as the well-based one,
   substituting document-specific components:

   | Component | Weight | Rule |
   |---|---|---|
   | `status_component` | 0.40 | `1.0` (the search itself executed without error) |
   | `presence_component` | 0.30 | `1.0` if any chunks were found, else `0.0` |
   | `similarity_component` | 0.20 | Mean similarity across returned chunks, `0.0` if none |
   | `provenance_component` | 0.10 | `1.0` if chunks span 2+ distinct file names, `0.5` if one, `0.0` if none |

   `factors["document_search"] = True` marks this path explicitly.

2. **Combined query (well/SODIR intent + `search_text`)** - the existing
   well-based formula (`docs/query_graph.md`) runs completely unchanged,
   using only `ResolutionResult`. Document evidence is recorded
   **advisory-only**: `factors["document_evidence_count"]` and
   `factors["document_similarity_mean"]` are added to the `factors` dict
   for inspection, but never enter the weighted `value` - a combined
   query's numeric confidence for the well/SODIR portion is identical to
   what it would be without `search_text`.

## Provenance

`QueryResponse.provenance` starts from `ResolutionResult.sources` (well
formula, unchanged) and then appends any additional source systems
`fuse_evidence` discovered - in practice, `"DOCUMENT"` whenever document
evidence was found. For `document_search`, `resolution_result` is `None`
so provenance is built entirely from document evidence
(`["DOCUMENT"]`).

## Tests

- `tests/test_document_retrieval.py` - `DocumentFilters`, ranking (no
  database), plus integration tests against the real
  `geo_intelligence` database (skipped if unavailable).
- `tests/test_query_graph.py` - `document_search` resolver-skip,
  evidence building, zero-result handling, retrieval failure handling,
  validation failure, and combined-query evidence merging.
- `tests/test_evidence.py` - document evidence fusion, provenance
  mapping, missing-info handling, rationale, and combined
  document+well evidence coexistence.

## Evaluation

`data/evaluation/golden_queries.json` adds 9 queries: `ds-01`..`ds-04`
(document-only, including a zero-result filter edge case), `ds-05`/`ds-06`
(validation failures), and `cb-01`/`cb-02` (combined well+document
queries). Three new metrics in `evaluation/metrics.py`:

- `document_result_presence` - did a document-tagged query with an
  expected minimum chunk count actually return that many chunks?
- `document_provenance_completeness` - is `"DOCUMENT"` present in
  provenance whenever document results were expected?
- `document_hit_at_k` - did the expected file name appear among the
  top-`k` returned chunks?

Run `python -c "from evaluation.runner import run_structured_evaluation;
print(run_structured_evaluation().pass_rate)"` to reproduce - all 37
golden queries (28 well/SODIR + 9 document/combined) pass at 100%.

## Known limitations

- Only one sample document (`sample_well_report.txt`, 2 chunks) has been
  ingested into the shared `geo_intelligence` database so far - golden
  queries are written against its actual content. Ingesting more
  documents does not require any change to this layer.
- `document_chunks.embedding` has an `ivfflat` index
  (`db/005_ingestion_pipeline_schema.sql`), which is unreliable at very
  small row counts (the same "over-filtering" issue documented in
  `retrieval/vector_search.py`). `document_retrieval/search.py` forces an
  exact sequential scan (`SET LOCAL enable_indexscan/enable_bitmapscan =
  off`) for the same reason, at negligible cost at this project's scale.
- Natural-language (Groq-interpreted) document queries are not yet
  wired up - `llm/prompts.py` does not know about `document_search` or
  `search_text`. All document and combined golden queries currently run
  through the deterministic `run_structured_query` path only. Adding
  Groq awareness of the new intent/field is future work and does not
  require any change to `document_retrieval/`, `graph/`, or `evidence/`.
