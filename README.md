# eRTMAC-NWIS — Nearby Wells Intelligence System

Evidence-first offset-well intelligence for drilling engineers: find nearby and geologically similar wells, see what went wrong on them, and get a traceable risk view before the bit gets there.

![Python](https://img.shields.io/badge/Python-3.13-3776AB) ![FastAPI](https://img.shields.io/badge/FastAPI-backend-009688) ![PostgreSQL](https://img.shields.io/badge/PostgreSQL-pgvector-336791) ![React](https://img.shields.io/badge/React-19-61DAFB) ![Vite](https://img.shields.io/badge/Vite-8-646CFF)

## Live demo

**https://ertmac-nwis-sih.vercel.app**

- Pick a role on the login screen ("Drilling Engineer" is the main one). The login is a demo role picker, not real authentication.
- The demo runs on free hosting. If nobody has used it for a while, the backend sleeps, so **the first request can take up to 30 seconds**. Later requests are fast.
- API docs (Swagger): https://ertmac-nwis-sih.onrender.com/docs

## Overview

Before drilling, engineers want to know what happened in nearby offset wells: mud losses, stuck pipe, pressure problems, which formations caused them, and at what depth. That knowledge is spread across structured well data (formation tops, mud records, casing, well logs) and unstructured reports (PDFs, scans, text). It is slow to search by hand and hard to trust when the source is unclear.

eRTMAC-NWIS puts both kinds of data into one PostgreSQL database and makes them queryable. It finds nearby wells by distance, finds similar wells using vector search over well-log features, extracts drilling events from wellbore history text, scores risk with transparent rules, and searches ingested documents. Every answer carries its evidence, source, and a confidence label so an engineer can check it.

## SIH 2026 details

| | |
|---|---|
| Event | Smart India Hackathon (SIH) 2026 |
| Organization | Oil India Limited (OIL) |
| Problem Statement | 2612 |
| Category | Software |
| Theme | Smart Automation |

## Key features

### Ingestion
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
        React + Vite frontend (map, panels, evidence drawer)
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
| Frontend | React 19, TypeScript, Vite 8, Tailwind CSS 4, TanStack Query, MapLibre GL, Recharts |
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
├── frontend/            React + Vite app
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
- Ingestion pipeline with OCR and handwriting classification
- Nearby and similar well search
- Drilling event extraction and correlation
- Evidence-based risk scoring and alerts
- LangGraph query workflow with evidence, rationale, and confidence
- Golden-query evaluation framework (29 queries)
- REST API and React frontend
- Hosted demo (Neon, Render, Vercel)

Planned:
- Real authentication and authorization (the login is a demo role picker, and the API has no auth layer yet)
- Handwriting transcription with a real handwriting OCR provider
- More labelled drilling events, then a trained risk model if the data supports it
- A repeatable database build from scratch (the base schema is not in version control yet)
- Real-time depth telemetry input

## Contributing

Open a pull request against `main` from a feature branch. Use short, imperative commit messages, for example `Add nearby-well radius filter`.

## Team

[Team name and members — to be added]

## License

[To be added]

## Acknowledgments

- Smart India Hackathon 2026
- Oil India Limited (OIL), problem statement 2612
- FORCE 2020 Machine Learning competition well-log dataset — https://github.com/bolgebrygg/Force-2020-Machine-Learning-competition
- Equinor Volve data village — https://www.equinor.com/energy/volve-data-sharing
- SODIR (Norwegian Offshore Directorate) fact pages — https://factpages.sodir.no
