# Docker deployment

Containerized deployment of the existing eRTMAC-NWIS stack — no
application logic changed. See `docker-compose.yml`, `Dockerfile.backend`,
`Dockerfile.frontend`, `nginx.frontend.conf`, `docker/initdb/00_init.sh`.

## Architecture

```
Browser
   |
frontend  (nginx, serves the built React app, proxies /api/* -> backend)
   |
backend   (FastAPI/uvicorn, api.app:app)
   |
postgres  (pgvector/pgvector:pg17)
```

Containers talk to each other by **compose service name**
(`postgres`, `backend`), never `localhost` — inside a container,
`localhost` only ever means that container itself. The backend's own
`db_config.py`/`api/config.py` default to `localhost:5433` (the
project's existing local-dev Postgres) specifically so nothing changes
for anyone running the app outside Docker; `docker-compose.yml`
overrides those with `DB_HOST=postgres` / `DB_PORT=5432` for the
containerized backend only.

## Prerequisites

- Docker Desktop (or Docker Engine + Compose plugin) — `docker compose version`
- A `.env` file at the repo root (copy `.env.example` and fill in
  `POSTGRES_PASSWORD`; `GROQ_API_KEY` is optional — see
  `docs/backend_api.md`)

## Commands

```bash
# First run (builds images, starts everything, follows logs)
docker compose up --build

# Subsequent runs, in the background
docker compose up -d

# Follow logs
docker compose logs -f

# Follow one service's logs
docker compose logs -f backend

# Stop (containers removed, named volume — and its data — kept)
docker compose down

# Rebuild after a code change
docker compose up --build
```

**Database reset** (only if you explicitly want to discard all
Dockerized Postgres data and start from an empty schema):

```bash
docker compose down -v   # removes the pgdata named volume too
docker compose up --build
```

## Ports

| Service | Container port | Host port | Notes |
|---|---|---|---|
| frontend | 80 (nginx) | 3000 | http://localhost:3000 |
| backend | 8000 (uvicorn) | 8000 | http://localhost:8000/health, /docs |
| postgres | 5432 | 55432 | Optional — only needed for direct `psql`/`pg_dump` access from the host. Deliberately not 5433, so it never collides with an existing native Postgres already running there. |

Only these three ports are published; all inter-container traffic stays
on the internal `nwis` bridge network.

## Environment variables

See `.env.example` for the full annotated list. The ones that matter for
Docker specifically:

| Variable | Used by | Purpose |
|---|---|---|
| `POSTGRES_DB` / `POSTGRES_USER` / `POSTGRES_PASSWORD` | postgres container (seeds it on first start) + backend container (connects with the same credentials) | Required — compose fails fast with a clear error if `POSTGRES_PASSWORD` is unset |
| `GROQ_API_KEY` | backend container | Optional. Unset → `/query` returns 503 and the frontend automatically falls back to `/query/structured` (existing, unmodified behavior — see `docs/backend_api.md`) |
| `API_CORS_ORIGINS`, `API_LOG_FORMAT` | backend container | Optional overrides, same as local dev |

**Never** set `GROQ_API_KEY` or any `POSTGRES_*`/`DB_*` value in the
frontend service — it has none, by design, and never reads `.env`.
`.dockerignore` (both the root one and `frontend/.dockerignore`) also
excludes `.env*` from every build context, so a secret can't
accidentally end up baked into an image layer even if compose's env
substitution weren't already scoped per-service.

## Database initialization

**Important, verified finding:** `db/001_create_geointelligence_schema.sql`
through `db/007_handwriting_detection.sql` are the project's existing,
unmodified migrations, and every statement in them is
`IF NOT EXISTS`/`ADD COLUMN IF NOT EXISTS` — but they are **not**
sufficient to bootstrap a genuinely empty database. Migration
`003_sodir_knowledge_layer.sql`'s own docstring says the foundational
`core.company`/`core.field`/`core.wellbore`/`core.discovery`/
`core.production_licence`/`core.wellbore_company` tables and
`subsurface.formation`/`formation_top`/`log_curve`/`log_measurement`
"already exist" in the environment it was written against. Confirmed by
actually running these migrations against a fresh Docker Postgres: 001
and 002 succeed (they only touch the self-contained `geointelligence`
schema), then 003 fails with `ERROR: schema "subsurface" does not
exist`. That foundational schema is not created by any file in this
repository — no `db/*.sql`, no Python script — it exists only as
already-applied state in whichever Postgres instance this project has
been developed against. This is exactly the "migrations are currently
manual" case the project's own conventions anticipate; the honest fix is
documenting the real initialization path, not inventing a schema
definition with no source of truth to check it against.

`docker/initdb/00_init.sh` therefore only runs
`CREATE EXTENSION IF NOT EXISTS vector;` automatically (Postgres's own
`docker-entrypoint-initdb.d` convention — runs once, only against a
genuinely empty data directory, never re-runs against existing data).
It does **not** auto-apply `db/*.sql`.

### Getting a fully working, data-populated Dockerized Postgres

**The reliable path** (what this project's own Docker verification
used): restore a `pg_dump` of an already-complete instance — one that
already has the foundational schema plus all of `db/001...007` applied,
plus real FORCE-2020/Volve/SODIR data (e.g. the Homebrew Postgres at
`localhost:5433` used throughout this project's local development):

```bash
pg_dump -h localhost -p 5433 -U prasadhemadri99 -d geo_intelligence -Fc -f geo_intelligence.dump
pg_restore -h localhost -p 55432 -U nwis -d geo_intelligence --clean --if-exists geo_intelligence.dump
```

This one step reproduces the foundational schema, every `db/*.sql`
migration's effect, and real data — because the source instance already
has all three. It never bakes the dump file into any image; it's a
one-time, host-side copy between two Postgres instances over the
network, using the host-published ports (`55432` for the Docker
Postgres, `5433` for the existing local one).

**If you don't have an existing populated instance to dump from** (a
genuinely from-scratch setup), you have two options, neither of which
this repository can fully automate today:

1. Recreate the foundational `core.*`/`subsurface.formation*`/
   `subsurface.log_*` schema yourself (this project's SODIR knowledge
   graph design, `docs/sodir_knowledge_graph_design.md`, documents what
   it expects to exist), then manually apply `db/001...007` in order —
   they're still mounted read-only at
   `/docker-entrypoint-initdb.d/db-migrations` inside the postgres
   container for exactly this purpose:
   ```bash
   for f in db/*.sql; do
     docker compose exec -T postgres psql -U nwis -d geo_intelligence -f "/docker-entrypoint-initdb.d/db-migrations/$(basename "$f")"
   done
   ```
2. Run the project's existing ETL scripts (`extract_sodir.py`,
   `build_embeddings_reduced.py`, `load_sodir_knowledge_graph.py`,
   `canonicalize_volve.py`, etc.) against the Dockerized Postgres
   (`localhost:55432`) — but note these were written and only ever run
   against the original foundational schema already being present, so
   this still depends on option 1 having been done first.

## Dataset mounting

`data/` (≈2.1GB — FORCE-2020/Volve/SODIR source files, embeddings,
unified feature parquet) is **never** copied into any image
(`.dockerignore` excludes it, and no Dockerfile has a `COPY data/ ...`
step). Exactly one runtime code path reads from it —
`risk/evidence_sources.py`'s caliper-washout evidence lookup, which
already catches the failure and returns an empty evidence list if the
file is missing, degrading risk assessments gracefully rather than
crashing.

`docker-compose.yml` mounts it read-only into the backend container
(`./data:/app/data:ro`) so that evidence source works identically to
local dev. If you don't have (or don't need) the full dataset on the
machine running Docker, remove that volume line — nothing else in the
container depends on it.

## Healthchecks

- **postgres**: `pg_isready -U $POSTGRES_USER -d $POSTGRES_DB`, checked
  every 5s, 10 retries.
- **backend**: `curl -f http://localhost:8000/health`, checked every
  10s after a 15s start period, 6 retries. This is the same `/health`
  endpoint documented in `docs/backend_api.md` — it reports
  `{"status": "ok", "database": "connected"}` when it can reach
  Postgres, `"unreachable"` if it can't (degraded, not crashed).
- **backend depends on postgres being healthy** (`condition:
  service_healthy`), so the backend never starts trying to serve
  traffic before Postgres can accept connections.
- **frontend depends on backend being healthy** for the same reason.

## Local development (unchanged)

Docker is an additional deployment path, not a replacement for local
dev:

```bash
# Backend
source venv/bin/activate
uvicorn api.app:app --reload --host 127.0.0.1 --port 8000

# Frontend
cd frontend && npm run dev
```

Both continue to default to `localhost:5433` exactly as before — no
`.env` changes are required to keep working locally without Docker.
