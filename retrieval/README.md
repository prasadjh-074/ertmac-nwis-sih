# Retrieval Library

Deterministic, cosine-similarity retrieval over the FROZEN, leakage-reduced
(30-dimensional) core embedding, stored in PostgreSQL + pgvector:

- `geointelligence.window_embeddings`
- `geointelligence.well_embeddings`

No LLM, no query planning, no reranking model, no learned ranking, no
frontend/backend. This is a plain Python library you can import and test
independently (`tests/test_retrieval.py`, `examples/retrieval_demo.py`).

## Modules

- **`filters.py`** — pure, DB-free dataclasses (`WindowFilters`, `WellFilters`)
  that compile optional metadata constraints (dataset, well_id,
  `min_curves_present`, `min_pooling_fraction`, self-exclusion) into SQL
  WHERE-clause fragments + bind parameters. Fully unit-testable without a
  database connection.
- **`ranking.py`** — `WindowResult` / `WellResult` dataclasses and the
  functions that turn already cosine-ordered DB rows into ranked, explainable
  result objects. Ranking is *only* cosine similarity (descending); rank is
  just the 1-indexed position in that order.
- **`vector_search.py`** — the only module that talks to PostgreSQL.
  `search_similar_windows(...)` / `search_similar_wells(...)` run
  `embedding <=> query::vector` (pgvector cosine distance) with every
  filter pushed into the SQL `WHERE` clause and `LIMIT top_k` applied by
  Postgres, never by fetching an oversized result set and trimming it in
  Python. Also discovers the embedding dimension from the data
  (`get_embedding_dimension`) instead of hard-coding it, and validates every
  query vector against that discovered dimension
  (`InvalidVectorDimensionError` on mismatch).
- **`hybrid_search.py`** — `hybrid_window_search` / `hybrid_well_search`
  are, deliberately, thin wrappers around the vector-search functions:
  ranking is cosine similarity, filters are hard constraints, and no
  weighting formula has been invented yet (per this stage's scope). Also
  provides query-by-example: `search_similar_windows_by_id` /
  `search_similar_wells_by_id` fetch a stored vector by key and search for
  its neighbors, always excluding the query object itself from its own
  results (enforced in SQL, not by filtering the result list after the
  fact).

## Quick start

```python
import retrieval as r

# Query-by-example: find windows similar to a real FORCE window
results = r.search_similar_windows_by_id(
    dataset="FORCE_2020", well_id="15/9-13 Sleipner East Appr", window_id=4,
    top_k=5,
)
for res in results:
    print(res.rank, res.dataset, res.well_id, res.window_id, f"{res.similarity:.3f}")

# Direct vector query with metadata filters (pushed into SQL)
query_vector = r.fetch_window_vector("VOLVE", "15/9-F-1", 160)
results = r.hybrid_window_search(
    query_vector, top_k=10, dataset="FORCE_2020", min_curves_present=6,
)
```

## Explainability

Every `WindowResult` carries `similarity`, `dataset`, `well_id`,
`depth_start_m`/`depth_end_m`, `curves_present`, and `embedding_type`.
Every `WellResult` carries `similarity`, `dataset`, `well_id`,
`windows_total`/`windows_pooled`/`windows_excluded`, and `pooling_fraction`.
That is enough to say *why* a result was returned (how similar, from which
dataset/well/depth, how much curve data backed it) without generating any
natural-language explanation — that's explicitly out of scope here.

## A correctness fix worth knowing about: HNSW + selective filters

During testing, `search_similar_windows(vector, dataset="VOLVE")` came back
**empty** despite 1,487 real Volve rows existing. `EXPLAIN ANALYZE` showed why:
pgvector's HNSW `ORDER BY ... LIMIT k` plan only scans the index's approximate
nearest candidates (`hnsw.ef_search`, default 40) and applies the `WHERE`
filter *after* that scan - not before. With Volve at ~8% of the table, none
of those 40 approximate candidates happened to be Volve rows, so the filter
removed all of them: zero results, even though the true answer set is large.
This is a known pgvector "over-filtering" limitation for selective
predicates, not a bug in the filter SQL.

Fix applied in `vector_search._execute_exact_vector_query`: every query in
this library runs with `enable_indexscan`/`enable_bitmapscan` turned off for
that statement, forcing an exact sequential scan + sort instead of the
approximate index. At this project's scale (tens of thousands of rows) this
costs ~5-6ms (measured), and a deterministic retrieval layer should return
the *true* nearest neighbors, not an approximation that can silently drop
valid results under a filter. The HNSW indexes still exist on both tables
(built per instructions) for when row counts grow enough that this tradeoff
needs revisiting - see the code comment for the full EXPLAIN ANALYZE trail.

## What this is not (yet)

- No arbitrary similarity-weighting formula — `hybrid_*` ranks by cosine
  similarity alone; filters only narrow the candidate set.
- No LLM query planning, no reranking model, no learned retrieval.
- No frontend/backend/API — this is a library, exercised by
  `tests/test_retrieval.py` and `examples/retrieval_demo.py`.
- No PCA, no changes to the embeddings themselves — this layer only reads
  `geointelligence.window_embeddings` / `geointelligence.well_embeddings`.
