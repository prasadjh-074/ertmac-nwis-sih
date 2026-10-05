# eRTMAC-NWIS — Nearby Wells Intelligence System

Evidence-first offset-well intelligence for drilling engineers: find nearby and geologically similar wells, see what went wrong on them, and get a traceable risk view before the bit gets there.

![Python](https://img.shields.io/badge/Python-3.13-3776AB) ![FastAPI](https://img.shields.io/badge/FastAPI-backend-009688) ![PostgreSQL](https://img.shields.io/badge/PostgreSQL-pgvector-336791) ![TypeScript](https://img.shields.io/badge/TypeScript-7-3178C6?logo=typescript&logoColor=white) ![CSS](https://img.shields.io/badge/CSS-Tailwind_4-06B6D4?logo=tailwindcss&logoColor=white) ![React](https://img.shields.io/badge/React-19-61DAFB?logo=react&logoColor=white)

## Live demo

**https://ertmac-nwis-sih.vercel.app**

- Pick a role on the login screen ("Drilling Engineer" is the main one). The login is a demo role picker, not real authentication.
- The demo runs on free hosting. If nobody has used it for a while, the backend sleeps, so **the first request can take up to 30 seconds**. Later requests are fast.
- The hosted demo is a reduced deployment. The ingestion pipeline is not available online, and the database holds only a processed subset of the data. See [Deployment challenges and known limitations](#deployment-challenges-and-known-limitations).
- API docs (Swagger): https://ertmac-nwis-sih.onrender.com/docs

## Overview

Before drilling, engineers want to know what happened in nearby offset wells: mud losses, stuck pipe, pressure problems, which formations caused them, and at what depth. That knowledge is spread across structured well data (formation tops, mud records, casing, well logs) and unstructured reports (PDFs, scans, text). It is slow to search by hand and hard to trust when the source is unclear.

eRTMAC-NWIS puts both kinds of data into one PostgreSQL database and makes them queryable. It finds nearby wells by distance, finds similar wells using vector search over well-log features, extracts drilling events from wellbore history text, scores risk with transparent rules, and searches ingested documents. Every answer carries its evidence, source, and a confidence label so an engineer can check it.

## SIH 2026 details

| | |
|---|---|
| Event | Smart India Hackathon (SIH) 2026 |
| Organization | Oil India Limited (OIL) |
| Problem Statement | 26121 |
| Category | Software |
| Theme | Smart Automation |

## Key features

### Ingestion
> **Availability:** the ingestion pipeline is fully implemented and tested in the codebase, but it is **not available in the hosted demo** because of backend resource constraints (see [Deployment challenges](#deployment-challenges-and-known-limitations)). It runs locally, and we will bring it online as soon as we have adequate server support.

- Loads PDFs, plain text, and scanned images, with Tesseract OCR and PyMuPDF for text extraction.
- Classifies each page as typed, handwritten, or mixed. It does not transcribe handwriting unless an OCR provider for it is available; otherwise the page is marked as unavailable.
- Extracts entities and relations with deterministic rules (regex and dictionaries), normalizes names and units, and resolves entities against reference tables.
- Splits text into chunks and stores 384-dimension embeddings (`all-MiniLM-L6-v2`) in pgvector, with page-level provenance.
- Status: demo / MVP. The reference tables (`ref_*`) are a small hand-seeded stand-in for the real SODIR/Volve schema.

### Offset-well intelligence
- Nearby wells by great-circle (Haversine) distance.
- Similar wells by cosine search over 30-dimension well and window embeddings built from well-log curve statistics.
- A combined view that shows the distance and similarity scores separately.
- Drilling events (10 event types) extracted from SODIR wellbore history text, each with severity, depth, formation, and source.
- Correlation of historical events with the current well by proximity, depth, and formation.

### Frontend workstation
A role-aware, desktop-first workstation for two roles: Drilling Engineer (operational intelligence) and System Administrator (platform administration, with no operational data).
- Interactive MapLibre well map showing the current, nearby, and similar wells, with a radius control and a well detail panel.
- Well search with filters, plus an engineer override for the current depth and formation.
- Risk matrix, alerts with a "Why this alert" evidence drawer, and a depth-based event timeline.
- Event correlation with a depth-versus-distance chart and formation search.
- AI assistant with query history and map highlighting. When the language model is unavailable, it falls back to the deterministic structured query.
- Document search with page-level provenance.
- Administrator pages for service health, users and roles, access policies, and security posture.
- Capabilities that are mocked or unavailable are labelled as such; the interface never invents data.

### Real-time decision support
- Evidence-based risk scoring and alerts (mud loss, stuck pipe, kick/overpressure, and others). This is rule-based, not machine learning: the project has only 31 labelled events across 20 wells, too few to train a model. See `docs/risk_intelligence.md`.
- Natural-language questions through a LangGraph workflow. The LLM (Groq) only turns a question into a validated structured query. It never writes SQL and never answers the question itself.
- A deterministic `/query/structured` endpoint that works with no LLM.
- Every response includes evidence, a rationale, and a heuristic confidence value (not a calibrated probability).
- Document search over ingested reports, with file name and page number on every result.

## Architecture

```
 PDFs / text / scans              SODIR + FORCE 2020 + Volve well data
        |                                        |
        v                                        v
 OCR (Tesseract) + handwriting          normalization + embeddings
 detection -> entity/relation                     |
 extraction -> resolution                         |
        |                                        |
        +------------------+---------------------+
                           v
        +----------------------------------------------+
        | PostgreSQL                                   |
        |  - SODIR knowledge layer (core, subsurface)  |
        |  - pgvector: 30-dim well/window embeddings   |
        |  - pgvector: 384-dim document embeddings     |
        |  - drilling events, identity links           |
        +----------------------------------------------+
                           |
    +-----------+----------+-----------+-------------+
    v           v          v           v             v
 Nearby     Similarity   Drilling    Risk        Document
 wells      (vector)     events      scoring     retrieval
    \___________\_________|__________/_____________/
                           v
        LangGraph query workflow
        interpret -> validate -> resolve -> collect evidence
        -> retrieve documents -> fuse -> confidence -> response
                           |
                           v
              FastAPI  (REST, JSON, request IDs)
                           |
                           v
        React + Vite frontend (role-aware workstation: map, risk, events, AI, documents, admin)
```

The two vector spaces (30-dim well data and 384-dim documents) are stored in separate tables and are never compared or mixed.

## Tech stack

| Layer | Technology |
|---|---|
| Backend | Python 3.13, FastAPI, Uvicorn, Pydantic |
| Database | PostgreSQL (extensions: pgvector, pgcrypto, uuid-ossp) |
| Vector search | pgvector, cosine distance |
| AI / ML | Groq LLM (query interpretation only), LangGraph, sentence-transformers |
| Document AI | Tesseract OCR, PyMuPDF, custom handwriting classifier |
| Frontend | React 19, TypeScript, Vite 8, Tailwind CSS 4, TanStack Query, MapLibre GL, Recharts, Lucide icons |
| Deployment | Docker, Neon, Render, Vercel |

## Repository structure

```
.
├── api/                 FastAPI app, settings, error handling, routers
├── db/                  SQL migrations 001-007
├── docker/              Postgres init script for docker compose
├── docs/                Design notes for each module
├── document_retrieval/  Semantic search over document chunks (384-dim)
├── evaluation/          Golden-query evaluation framework (29 queries)
├── events/              Drilling event extraction, storage, correlation
├── evidence/            Evidence fusion, provenance, rationale
├── examples/            Small demo scripts
├── features/            Feature schema for the well-log windows
├── frontend/            React + Vite role-aware workstation (src/features, src/hooks, src/auth)
├── graph/               LangGraph query workflow
├── ingestion/           OCR, NLP, handwriting detection, storage pipeline
├── llm/                 Groq interpreter: question -> structured query
├── metadata/, qc/       Well metadata and data-quality summaries (CSV)
├── nearby/              Haversine nearby search, combined nearby+similar
├── query/               Structured query contract and validator
├── resolver/            Structured query -> deterministic data retrieval
├── retrieval/           Vector search over well and window embeddings
├── risk/                Rule-based risk scoring and alerts
├── tests/               Pytest suite
├── db_config.py         Database connection settings
├── Dockerfile.backend, Dockerfile.frontend, docker-compose.yml
└── requirements.txt
```

Not in the repo (git-ignored): `data/`, `normalized/`, `windows/`, `venv/`, `.env`.

## API endpoints

Base URL: `https://ertmac-nwis-sih.onrender.com` (interactive docs at `/docs`).

| Method | Path | Purpose |
|---|---|---|
| GET | `/health` | Liveness and database reachability |
| GET | `/wells` | List wells, filter by dataset |
| GET | `/wells/lookup` | One well's location and details |
| GET | `/wells/nearby` | Wells within a radius (km) |
| GET | `/wells/similar` | Geologically similar wells |
| GET | `/wells/context` | Nearby and similar wells together |
| GET | `/wells/state` | Current well state snapshot |
| GET | `/events/well` | Drilling events for a well |
| GET | `/events/near-depth` | Events near a depth |
| GET | `/events/formation` | Events by formation |
| GET | `/events/correlated` | Historical events correlated to the current well |
| GET | `/risk/assess` | Evidence-based risk assessment |
| GET | `/risk/alerts` | Alerts with recommendations |
| POST | `/documents/search` | Semantic search over document chunks |
| GET | `/documents/{id}` | Document metadata and handwriting summary |
| POST | `/query` | Natural-language question (needs `GROQ_API_KEY`) |
| POST | `/query/structured` | Structured query, no LLM |

Full details: `docs/backend_api.md`.

## Deployment

The hosted demo uses three free-tier services.

- **Database — Neon.** PostgreSQL with the pgvector extension, region `us-east-2` (Ohio). Loaded from a `pg_dump` of the local database (about 48 MB).
- **Backend — Render.** Docker web service built from `Dockerfile.backend`, Ohio region, health check on `/health`.
- **Frontend — Vercel.** Vite build from the `frontend/` directory. `frontend/vercel.json` rewrites `/api/*` to the Render backend, so the browser only talks to one origin and no CORS setup is needed.

Source data is the public FORCE 2020 well-log dataset from Norway (plus Volve and SODIR data, see Data).

## Deployment challenges and known limitations

We built and verified the full system locally against about 2.1 GB of source data. Deploying it on free-tier infrastructure forced us to cut what we could host. This section is an honest account of what that means for the live demo.

### What we faced

| Challenge | Detail |
|---|---|
| Limited database | Only a processed `pg_dump` of about 48 MB was pushed to Neon. The raw data (about 2.1 GB, including roughly 2.3 million FORCE 2020 depth rows and the SODIR source files) was not hosted. |
| Backend lag | The free Render service sleeps when idle. The first request can take 30 seconds or more, and some heavier calls (document search, event queries, natural-language `/query`) exceeded 100 seconds or timed out in our checks. |
| Reduced coverage online | The hosted API lists 113 FORCE 2020 wells and 12 Volve wells, and no SODIR wells. Several wells return few or no extracted events, so risk output there is based on limited evidence and carries lower confidence. |
| Heavy workloads | OCR, embedding generation, and large vector searches need more memory and compute than the free tier gives. |

### What is affected in the live demo

- **Ingestion pipeline: unavailable online.** OCR, handwriting classification, entity extraction, and document embedding are implemented but cannot run within the current backend limits. Only one sample document is ingested, so document search is minimal and slow.
- **Natural-language queries (`/query`):** slow or timing out. The hosted server also has no working Groq key. The deterministic `/query/structured` endpoint works and is used as the fallback.
- **SODIR data:** designed and validated locally, but not served by the hosted API.
- **Risk and events:** sparse for many wells because of the limited data loaded, not because of a logic fault.
- **Free-tier cold starts:** expect a delay on the first request after idle time.
- **Knowledge vault (Documents page):** it searches document text and has no per-well filter. Only one sample document is loaded, the report for well `30/6-1` (Equinor, licence PL 123, total depth 2890 m, with formation tops such as Heimdal and Sleipner). Search terms from that report return results; other wells return nothing relevant.
- **Backend crashes under document search:** in our checks, a document search request made the Render service return 502 (bad gateway) on `/health` and every other endpoint. It recovered on its own after roughly 40 seconds. Document search needs the embedding model in memory, so we suspect the free instance runs out of memory, but we have not confirmed this from the service logs.

### Demo tips for the hosted version

- Open the site a few minutes early and use a normal page (map or nearby wells) to wake the backend.
- On the Documents page, run a single search (for example "Heimdal") and wait for it to finish.
- If the backend returns 502, wait about a minute and retry.

### Our commitment

The ingestion pipeline works locally, and we will deploy it properly once we have server support: a larger database, an always-on backend with more memory, and a background worker for OCR and ingestion. With that support we would also load the full datasets, restore SODIR coverage, and enable the natural-language assistant. Until then, the full system can be run locally by following the setup steps below.

More detail: [docs/RESOURCE_CONSTRAINTS.md](docs/RESOURCE_CONSTRAINTS.md).

## Getting started (local development)

### Prerequisites
- Python 3.13
- Node.js 22 or newer, and Yarn
- PostgreSQL 17 or newer with the pgvector extension
- Tesseract OCR (only for the ingestion pipeline)
- Docker (optional)

### 1. Clone
```bash
git clone https://github.com/prasadjh-074/ertmac-nwis-sih.git
cd ertmac-nwis-sih
```
The repository is private, so you need access first.

### 2. Environment
```bash
cp .env.example .env
```
Edit `.env`. See Configuration below.

### 3. Database
The migrations in `db/` are not enough to build the database from nothing. Migration `003` and later assume the base `core.*` and `subsurface.*` tables already exist, and no file in this repo creates them. The reliable way to get a working database is to restore a dump of an existing instance:
```bash
psql "postgresql://USER:PASSWORD@HOST:PORT/DBNAME" -v ON_ERROR_STOP=1 --single-transaction -f geo_intelligence_dump.sql
```
Ask the team for the dump file. Details and alternatives are in `docs/docker.md` ("Database initialization").

### 4. Backend
```bash
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
uvicorn api.app:app --reload --port 8000
```
Check it: `curl http://localhost:8000/health`

### 5. Frontend
```bash
cd frontend
yarn install
yarn dev
```
The dev server runs on http://localhost:3000 and forwards `/api/*` to `http://127.0.0.1:8000`. Set `VITE_API_PROXY_TARGET` to point it somewhere else.

### Docker alternative
```bash
docker compose up --build
```
This starts Postgres (host port 55432), the backend (8000), and the frontend behind nginx (3000). `POSTGRES_PASSWORD` must be set in `.env`. The database starts empty with pgvector enabled; load data as described in step 3.

### Ingest a document
```bash
python -m ingestion.pipeline --input path/to/report.pdf --verbose
```
Options: `--source pdf|text|image` to override type detection.

### Tests
```bash
pytest
```
**Test results: 575 tests run, 575 passed, 0 failed** (Python 3.13, full local suite, about 2 min 40 s). The suite has 25 test files covering risk scoring, handwriting detection, drilling events, evidence and explainability, nearby wells, the REST API, the query contract and graph, the resolver, the Groq interpreter, document and vector retrieval, and every stage of the ingestion pipeline.

In addition, the golden-query evaluation set (29 queries) passed 29 of 29 in structured mode.

The frontend has no automated unit tests. It was checked by end-to-end flow testing of the main user journeys.

Tests marked `live` (need a real Groq key), `integration` (need a real database), and `slow` are opt-in. See `pytest.ini`.

## Configuration

| Variable | Purpose |
|---|---|
| `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, `DB_PASSWORD` | Database connection. If unset, defaults to `localhost:5433`, database `geo_intelligence`. |
| `PGSSLMODE` | Set to `require` for hosted databases such as Neon. |
| `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD` | Used by docker compose to create the Postgres container. Password is required. |
| `GROQ_API_KEY` | Enables `/query`. Optional; without it `/query` returns 503. |
| `GROQ_MODEL` | Groq model name for query interpretation. |
| `INGESTION_DATABASE_URL` | Database URL for the ingestion pipeline. |
| `OCR_ENABLED`, `OCR_LANGUAGE` | Turn OCR on or off; OCR language code. |
| `EMBEDDING_MODEL` | Sentence-transformer model for document embeddings. |
| `API_LOG_FORMAT`, `API_LOG_LEVEL` | Log format (`json` or `text`) and level. |
| `API_CORS_ORIGINS` | Comma-separated allowed origins. CORS is off by default. |
| `API_DB_POOL_MIN`, `API_DB_POOL_MAX` | Connection pool size. |
| `API_REQUEST_TIMEOUT_SECONDS` | Request timeout. |
| `PORT` | Port for the hosted container (`8000` on Render). |

Never commit `.env`. It is git-ignored.

## Data

The source data comes from three public Norwegian sources: the FORCE 2020 well-log dataset (118 wells, about 2.3 million depth rows in the normalized set), Equinor's Volve dataset, and SODIR (Norwegian Offshore Directorate) well records. The raw files are about 2.1 GB, so `data/`, `normalized/`, and `windows/` are git-ignored and not stored in this repository.

For local development you do not need the raw files. The database dump already contains the processed tables (about 48 MB). The backend reads `data/` at runtime in only one place, a caliper lookup in `risk/evidence_sources.py`, and it degrades gracefully if the files are missing (fewer risk evidence signals).

## Roadmap / status

Done:
- Ingestion pipeline with OCR and handwriting classification (implemented and tested locally; not deployed, see Deployment challenges)
- Nearby and similar well search
- Drilling event extraction and correlation
- Evidence-based risk scoring and alerts
- LangGraph query workflow with evidence, rationale, and confidence
- Golden-query evaluation framework (29 queries)
- REST API and role-aware React frontend (v2)
- Hosted demo (Neon, Render, Vercel)

Planned:
- Deploy the ingestion pipeline and the full datasets once server support is available
- Real authentication and authorization (the login is a demo role picker, and the API has no auth layer yet)
- Handwriting transcription with a real handwriting OCR provider
- More labelled drilling events, then a trained risk model if the data supports it
- A repeatable database build from scratch (the base schema is not in version control yet)
- Real-time depth telemetry input

## Contributing

Open a pull request against `main` from a feature branch. Use short, imperative commit messages, for example `Add nearby-well radius filter`.

## Team

| Name |
|---|
| Prasad Jagadish Hemadri |
| Prathigna S |
| Disha K |
| Gagana Shri R K |
| Keerthana G S |
| Vivek G |

## License

This project is licensed under the MIT License. See [LICENSE](LICENSE).

## Acknowledgments

- Smart India Hackathon 2026
- Oil India Limited (OIL), problem statement 26121
- FORCE 2020 Machine Learning competition well-log dataset — https://github.com/bolgebrygg/Force-2020-Machine-Learning-competition
- Equinor Volve data village — https://www.equinor.com/energy/volve-data-sharing
- SODIR (Norwegian Offshore Directorate) fact pages — https://factpages.sodir.no
