# Backend API (`api/`)

FastAPI backend for the eRTMAC-NWIS geological intelligence system.
Exposes the full stack — well lookup, geological similarity, historical
drilling events, evidence-based risk assessment, document retrieval,
and LangGraph-orchestrated natural-language / structured queries —
over HTTP.

## Why FastAPI, not Node.js

Every downstream module (LangGraph orchestration, Groq LLM interpreter,
pgvector search, risk engine, ingestion pipeline) is already Python.
FastAPI imports them directly, in-process, with no serialization
boundary. A Node.js layer would require either reimplementing all of
this in JS or running two stacks talking over HTTP/RPC — pure overhead
with no upside since none of Node's typical advantages (shared
frontend code, high-concurrency I/O) apply.

## Layout

```
api/
    app.py             — FastAPI app instance, lifespan, middleware wiring
    config.py           — env-driven settings, no hard-coded secrets
    deps.py             — connection pool + graph runner dependencies
    errors.py           — uniform structured error envelope
    logging.py          — structured JSON logging with request-ID context
    middleware.py       — request-ID + timing + access log
    schemas.py          — Pydantic response models
    routers/
        health.py       — GET  /health
        wells.py        — GET  /wells, /wells/lookup, /wells/nearby,
                                 /wells/similar, /wells/context, /wells/state
        query.py        — POST /query, /query/structured
        events.py       — GET  /events/well, /events/near-depth,
                                 /events/formation, /events/correlated
        risk.py         — GET  /risk/assess, /risk/alerts
        documents.py    — POST /documents/search, GET /documents/{id}
```

## Endpoints

### Health

  * `GET /health` — liveness probe. Reports database reachability.

### Wells (unchanged from earlier phases)

  * `GET /wells?dataset=&limit=`
  * `GET /wells/lookup?dataset=&well_id=`
  * `GET /wells/nearby?dataset=&well_id=&radius_km=&limit=&dataset_filter=`
  * `GET /wells/similar?dataset=&well_id=&top_k=&dataset_filter=`
  * `GET /wells/context?dataset=&well_id=&radius_km=&nearby_limit=&similar_limit=`
  * `GET /wells/state?dataset=&well_id=`

### Query (LangGraph)

  * `POST /query` — natural-language question. Requires
    `GROQ_API_KEY` (returns 503 otherwise).

    ```json
    { "question": "find wells similar to 15/9-F-1" }
    ```

  * `POST /query/structured` — deterministic structured-query entry
    point, bypasses the LLM entirely.

    ```json
    {
      "structured_query": {
        "intent": "similar_wells",
        "target_dataset": "VOLVE",
        "target_well_id": "15/9-F-1",
        "top_k": 5
      }
    }
    ```

    The payload's `structured_query` is validated against
    `StructuredQuery` (`extra="forbid"`, every field enum/regex/bounded)
    before any DB call runs. Unknown fields are rejected with 422.

### Events

  * `GET /events/well?dataset=&well_id=&event_type=`
  * `GET /events/near-depth?dataset=&well_id=&depth_m=&tolerance_m=&event_type=`
  * `GET /events/formation?formation=&dataset=&well_id=&event_type=`
  * `GET /events/correlated?dataset=&well_id=&current_depth_m=&current_formation=&radius_km=&limit=&event_type=`

### Risk

  * `GET /risk/assess?dataset=&well_id=&current_depth_m=&current_formation=&radius_km=&limit=`
    — evidence-based assessments for all 5 risk types.
    Each result carries `methodology`, `limitations`,
    `model_or_rule_source` so callers do not misinterpret scores as
    calibrated probabilities.
  * `GET /risk/alerts?dataset=&well_id=&…` — alerts derived from
    assessments (above LOW) + triggered deterministic rules.

### Documents

  * `POST /documents/search` — semantic search over document chunks
    (384-dim sentence-transformer embeddings, separate vector space
    from the 30-dim well/window embeddings).

    ```json
    { "query": "mud loss zones", "top_k": 5, "source_type": "pdf" }
    ```

  * `GET /documents/{document_id}` — document metadata + handwriting
    summary per page (surfaces `handwriting_classification`,
    `handwriting_confidence`, `handwriting_ocr_status` for each page).

## Middleware

`RequestContextMiddleware` runs on every request:

| Header set on response | Purpose |
|---|---|
| `X-Request-ID` | Correlation ID. Forwarded verbatim if the client sends one; otherwise a fresh UUID hex is generated. Attached to every log line inside the request. |
| `X-Elapsed-Ms` | Wall-clock handler duration. |

A single access log line is emitted per request in JSON form:

```json
{"ts":"2026-09-28T13:14:54+0530","level":"INFO","logger":"api.access",
 "message":"request","request_id":"eda58...","path":"/health",
 "method":"GET","status":200,"elapsed_ms":12.5}
```

## Error envelope

Every error the API emits has the same shape:

```json
{
  "error": {
    "type":       "not_found",
    "message":    "Well VOLVE:MISSING not found",
    "status":     404,
    "request_id": "eda5895dba28462684f2bd2c4ee2e143",
    "detail":     null
  }
}
```

For 5xx responses the client always sees a generic
`"internal_server_error"` slug and `"An internal error occurred."`
message; the full traceback goes only to server logs. Internal detail
is never leaked to clients.

## Configuration

Every setting reads from the environment; there are no hard-coded
credentials.

| Env var | Default | Purpose |
|---|---|---|
| `API_DB_HOST` / `DB_HOST` | `localhost` | PostgreSQL host |
| `API_DB_PORT` / `DB_PORT` | `5433` | port |
| `API_DB_NAME` / `DB_NAME` | `geo_intelligence` | database name |
| `API_DB_USER` / `DB_USER` | `prasadhemadri99` | user |
| `API_DB_PASSWORD` / `DB_PASSWORD` | (unset) | password if any |
| `API_DB_POOL_MIN` | 1 | pool min connections |
| `API_DB_POOL_MAX` | 8 | pool max connections |
| `GROQ_API_KEY` | (unset) | enables /query (natural language) |
| `API_LLM_ENABLED` | auto | force-enable/disable /query |
| `API_CORS_ORIGINS` | (empty) | comma-separated list; CORS off if empty |
| `API_LOG_LEVEL` | `INFO` | log level |
| `API_LOG_FORMAT` | `json` | `json` or `text` |
| `API_REQUEST_TIMEOUT_SECONDS` | 60 | request handler timeout |

Values are loaded via `python-dotenv` from `.env` if present.
`.env` is in `.gitignore`. **Never commit `.env` or hard-code an API
key in source.**

## Security invariants

1. **No API keys / DB credentials in source.** Every credential comes
   from the environment.
2. **All SQL uses parameterized placeholders.** No user input is ever
   interpolated into a SQL string. The LLM never generates SQL — the
   `StructuredQuery` contract (`extra="forbid"`, enum/regex fields
   only) is the only path from natural language into a query.
3. **5xx responses never leak internals.** Tracebacks go to server
   logs; the client gets a generic message.
4. **CORS is off by default.** Enable only via explicit
   `API_CORS_ORIGINS`.
5. **No external cloud OCR / LLM used by default.** Groq is the only
   external service and is optional — /query returns 503 when not
   configured, and /query/structured is 100% local.

## Robustness

* **Connection pool** (`psycopg2.pool.SimpleConnectionPool`) is
  opened once at app startup and reused across requests. Each request
  borrows one connection via the `get_conn` dependency; commit /
  rollback / return-to-pool is handled by a context manager, so
  connections aren't leaked when a handler raises.
* **Graceful degradation.** If the DB pool can't be opened at startup
  (e.g. Postgres is down), the app still comes up; endpoints that
  need the DB report a 503 and `/health` returns `database:
  unreachable`. If Groq is not configured, only `/query` returns 503
  — everything else keeps working.
* **Request correlation.** Every log line inside a request carries
  the same `X-Request-ID`.
* **Structured logs.** JSON output by default for machine ingestion.
* **Uniform errors.** Every 4xx/5xx has the same envelope shape.

## Usage

### Run the server locally

```bash
source venv/bin/activate
export DATABASE_URL=postgresql://prasadhemadri99@localhost:5433/geo_intelligence
# Optional — enables /query natural-language endpoint
# export GROQ_API_KEY=sk_...
uvicorn api.app:app --reload --host 127.0.0.1 --port 8000
```

Interactive docs: `http://127.0.0.1:8000/docs`
OpenAPI spec: `http://127.0.0.1:8000/openapi.json`

### Example calls

```bash
# Liveness
curl -s http://127.0.0.1:8000/health

# Look up a well
curl -s 'http://127.0.0.1:8000/wells/lookup?dataset=VOLVE&well_id=15/9-F-1'

# Nearby wells within 30 km
curl -s 'http://127.0.0.1:8000/wells/nearby?dataset=VOLVE&well_id=15/9-F-1&radius_km=30&limit=5'

# Similar wells (pgvector cosine)
curl -s 'http://127.0.0.1:8000/wells/similar?dataset=VOLVE&well_id=15/9-F-1&top_k=5'

# Full context (well + nearby + similar in one call)
curl -s 'http://127.0.0.1:8000/wells/context?dataset=VOLVE&well_id=15/9-F-1'

# Historical drilling events for a well
curl -s 'http://127.0.0.1:8000/events/well?dataset=VOLVE&well_id=15/9-F-1'

# Correlated events (own well + nearby + depth + formation)
curl -s 'http://127.0.0.1:8000/events/correlated?dataset=VOLVE&well_id=15/9-F-1&current_depth_m=3200'

# Evidence-based risk assessment
curl -s 'http://127.0.0.1:8000/risk/assess?dataset=VOLVE&well_id=15/9-F-1&current_depth_m=3200'

# Alerts derived from those assessments + rules
curl -s 'http://127.0.0.1:8000/risk/alerts?dataset=VOLVE&well_id=15/9-F-1'

# Deterministic structured query (no LLM required)
curl -s -X POST http://127.0.0.1:8000/query/structured \
     -H "Content-Type: application/json" \
     -d '{"structured_query":{"intent":"similar_wells","target_dataset":"VOLVE","target_well_id":"15/9-F-1","top_k":5}}'

# Natural-language query (requires GROQ_API_KEY)
curl -s -X POST http://127.0.0.1:8000/query \
     -H "Content-Type: application/json" \
     -d '{"question":"which wells are geologically similar to 15/9-F-1"}'

# Semantic document search
curl -s -X POST http://127.0.0.1:8000/documents/search \
     -H "Content-Type: application/json" \
     -d '{"query":"mud loss at high pressure","top_k":5}'
```

### Response headers to expect

* `X-Request-ID` — correlation ID (send your own to trace across services)
* `X-Elapsed-Ms` — server handler time in ms
* `content-type: application/json`

## Tests

* **Unit-style** (`tests/test_api.py`, no DB required): middleware
  behaviour, error envelope shape, endpoint wiring, schema validation,
  dependency overrides.
* **Integration** (`@pytest.mark.integration`, real DB): end-to-end
  contracts, e.g. `TestNewRoutersIntegration::test_risk_assess_real`.

Run them:

```bash
python -m pytest tests/test_api.py -v            # unit + integration
python -m pytest tests/test_api.py -v -m 'not integration'   # unit only
python -m pytest tests/ -v                                    # full suite
```

**Latest run: 575 passed, 0 failed** — 545 pre-existing tests + 30
new API tests, no regressions.
