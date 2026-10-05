# Resource Constraints and Hosted-Demo Gaps

eRTMAC-NWIS is built and tested locally against about 2.1 GB of raw well data. The hosted demo (Neon + Render + Vercel) runs on free-tier infrastructure and cannot hold or serve all of it. This document records what is implemented but trimmed or unavailable online, and why.

Last checked against the live API: 2026-10-03.

## 1. The problem

| | Local / source | Hosted demo |
|---|---|---|
| Raw data | ~2.1 GB (`data/`: SODIR ~840 MB, FORCE 2020 ~1 GB, Volve ~214 MB) | Not hosted |
| Database | Full local PostgreSQL + pgvector | ~48 MB `pg_dump` loaded into Neon |
| Backend | Runs on a developer machine | Render free web service (Docker) |
| Frontend | Vite dev server | Vercel, `/api/*` rewritten to Render |

The raw files and the normalized depth-row tables (about 2.3 million rows for FORCE 2020) are git-ignored and are not in the hosted database. Only processed tables (wells, embeddings, extracted events, risk inputs, document chunks) were loaded.

## 2. What this costs us (observed)

- **Cold starts and timeouts.** Render's free tier sleeps idle services, so the first request can be very slow. In testing, `POST /documents/search` did not return within 100 s, and `GET /events/well` for a Volve well hung for over 100 s on a repeat call. The frontend PRD records the same issue for document search.
- **Wells with data but no results.** `GET /wells` returns 113 FORCE 2020 wells and 12 Volve wells. It returns 0 for `dataset=SODIR`. The full SODIR wellbore knowledge graph (see `docs/sodir_knowledge_graph_design.md`) is not served online.
- **Sparse events.** Drilling events come from regex extraction over wellbore history text. For Volve F-12, `/events/well` returns 0 events, so risk output relies on a handful of correlated events from neighbouring wells (3 for F-12). Risk scores come back with low-to-moderate confidence (0.55 for mud loss).
- **Documents.** Only one sample document (`sample_well_report.txt`, 2 chunks) is ingested (`docs/document_retrieval.md`). Document search is therefore not representative of the full ingestion pipeline.
- **Caliper evidence missing.** `risk/evidence_sources.py` reads raw files under `data/` for caliper lookups. Without them, hosted risk scores have fewer evidence signals.
- **Reduced embeddings.** Similarity search uses 30-dimension well and window embeddings (reduced set). Full-dimension and extended Volve embeddings (`data/embeddings/*_extended*`, `*_reduced*`) exist locally for ablation and leakage analysis but are not what the hosted index is built from.

## 2a. Knowledge vault and backend stability

- The Knowledge vault (Documents page) is a semantic search over document chunks with no per-well filter. The only ingested document is the sample report for well `30/6-1` (Equinor, licence PL 123, total depth 2890 m, formation tops including Heimdal and Sleipner). Other wells return nothing relevant.
- On 2026-10-05, `POST /documents/search` returned 502 and `/health` also returned 502 for the whole service. It recovered by itself after about 40 seconds. A second search attempt earlier in the same check also returned 502 within seconds. Likely cause: the embedding model does not fit in the free instance's memory (unconfirmed; check the Render logs for an out-of-memory message).
- The `15/9-19 A` events request returned a 500 error. The golden-query docs already list Volve 15/9-19 well IDs as a known limitation.
- Demo advice: wake the backend with a normal page first, run one document search at a time, and retry after about a minute if a 502 appears.

## 3. Implemented but held back (not available online)

| Feature | State | Why it is held back |
|---|---|---|
| Full FORCE 2020 depth-level curves (~2.3 M rows) | Implemented locally, normalized set | Too large for the free database tier |
| SODIR wellbore data and knowledge graph | Designed and validated locally | 0 SODIR wells served; ~840 MB source |
| Window-level (depth window) similarity over the full set | Implemented; `/query` supports `similar_windows` | Large `window_embeddings` tables; slow on shared compute |
| Leakage / ablation analysis of embeddings | Run locally (`data/embeddings/leakage_*`) | Offline analysis only, needs the full data |
| Corpus-scale document ingestion (OCR, handwriting classification) | Pipeline implemented | Only one sample document ingested; OCR is compute-heavy |
| Natural-language document queries | Not wired into the Groq prompt | Separate work, plus a Groq key that is invalid on the hosted server (per the frontend PRD) |
| Golden-query evaluation (29 queries) | Runs locally | Needs the full dataset and test DB |

## 4. Missing or limited on the live site

Based on the live API and the v2 frontend PRD:

1. **AI assistant (`POST /query`)**: natural-language interpretation depends on a Groq API key; the PRD reports it fails on the hosted server. The deterministic `/query/structured` path works and is used as a fallback. Slow responses (60 s+) were seen.
2. **Documents**: search times out on the free tier and has almost no content.
3. **SODIR wells**: no SODIR-dataset wells are listed, so SODIR-only queries return nothing.
4. **Events and risk for many wells**: sparse or empty events, so risk confidence is limited.
5. **Authentication**: the login is a demo role picker. The API has no auth layer.
6. **Admin pages**: no backend endpoints exist for metrics, audit log or ingestion status, so those screens show health-based tiles, a local audit log and "status unknown".
7. **Handwriting transcription**: handwriting is classified but not transcribed (no real handwriting OCR provider).
8. **Real-time depth telemetry**: not implemented; depth is entered manually as an override.
9. **Trained risk model**: risk is rule-based, since there are too few labelled events to train one.
10. **Reproducible DB build**: the base schema is not in version control, so the hosted DB can only be restored from a dump.

## 5. What would remove these limits

- Paid or higher-tier database (Neon) to host depth rows, SODIR data and full embeddings.
- Always-on backend instance (no sleep) with more memory, or a managed vector store.
- Move heavy OCR and ingestion to a background worker with a queue.
- Valid, server-side Groq key (or self-hosted LLM) stored as an environment secret.
- Pre-compute and cache expensive endpoints (documents, events, risk) for demo wells.
- Commit the base schema and a repeatable data-load script.
- Add authentication (SSO/JWT) and admin telemetry endpoints.

## 6. How to reproduce the full system

Run it locally with the full data (see the main README: Setup and Docker Compose). The local stack has none of the limits above.

---

*Figures in sections 1 and 2 come from the main README, the `docs/` folder and live API checks on 2026-10-03. Free-tier specifics (memory, sleep behaviour, storage caps) were not measured here; confirm them against your own Render and Neon plan before quoting numbers.*
