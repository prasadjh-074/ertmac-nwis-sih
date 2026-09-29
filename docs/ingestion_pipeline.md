# Ingestion Pipeline

**Status: DEMO / MVP.** Built for a hackathon-style vertical-slice demo, not
production use. See "Known Limitations" and "Future Production Improvements"
at the end of this document for what would need to change before this goes
anywhere near production.

## 1. Overview & Scope

This package (`ingestion/`) implements a modular OCR + NLP ingestion
pipeline that takes a geological/well document (PDF, plain text, or a scanned
image) and turns it into structured, resolved, provenance-tracked data in
PostgreSQL + pgvector:

```
Document -> OCR/text extraction -> text cleaning -> NLP entity extraction
    -> relation extraction -> normalization -> entity resolution
    -> validation -> PostgreSQL persistence -> chunking -> embeddings
    -> pgvector storage
```

Everything is deterministic (regex + dictionaries + simple heuristics) --
there is no model training, no fine-tuning, and no spaCy model download.
The project started from an empty repository (no pre-existing SODIR/Volve
schema, LangGraph workflow, or embedding abstraction existed), so this
package also includes minimal versions of those supporting pieces.

## 2. Folder Structure

```
ingestion/
    config.py          settings from environment variables
    schemas.py          shared pydantic data model (Entity, Relation, ...)
    loaders/             source detection + raw document loading
    preprocessing/       PDF text extraction (PyMuPDF), text cleaning
    ocr/                 OCRProvider abstraction + Tesseract implementation
    nlp/                 entity_extractor.py, relation_extractor.py
    normalization/       name/unit normalization, entity resolution
    validation/          validators.py
    chunking/            chunker.py
    embeddings/          EmbeddingProvider abstraction + sentence-transformers
    storage/             SQLAlchemy models, Postgres + pgvector writers
    provenance/          provenance metadata helper
    ontology/            entities.yaml, aliases.yaml, relationships.yaml, units.yaml
    graph/               LangGraph state + workflow
    pipeline/            run_pipeline() entrypoint + CLI
migrations/              hand-written SQL: reference stand-in schema + ingestion schema
scripts/apply_migrations.py   tiny migration runner
tests/                   unit tests + one end-to-end test
```

## 3. Supported Inputs

- **PDF** -- text-layer PDFs are extracted directly via PyMuPDF; pages with
  little/no extractable text (scanned pages) are rendered to an image and
  OCR'd instead. OCR is never forced on every page, only where needed.
- **Plain text** (`.txt`, `.md`) -- read directly.
- **Images** (`.png`, `.jpg`, `.tif`, ...) -- always OCR'd, since there's no
  embedded text layer to extract.

## 4. OCR Flow

`ingestion/ocr/ocr_provider.py` defines an `OCRProvider` interface
(`extract_text(image_bytes) -> OCRResult`), so the engine can be swapped
later. The only implementation is `TesseractOCRProvider`, which applies
light preprocessing (grayscale + autocontrast) before calling
`pytesseract.image_to_data` to also recover a mean confidence score. If the
`tesseract` binary or the `pytesseract` package isn't available, it returns
an `OCRResult` with `error` set (and `text=""`) instead of raising -- the
pipeline logs a warning and continues rather than crashing.

## 5. NLP Extraction

`nlp/entity_extractor.py` is entirely regex + dictionary based:

- Regex: well IDs (`30/6-1`), licences (`PL 123`), formation names with a
  `Fm`/`Formation` suffix, depths (`2890 m`, `TD`/`MD`/`TVD`/`TVDSS`),
  dates (several formats), simple production figures (`1200 bbl/d`).
- Dictionary/alias lookup (from `ontology/aliases.yaml`): companies
  (including historical names, e.g. "Statoil" -> "Equinor"), known
  formation names without a suffix (for tabular "formation tops" listings),
  fields, log curve codes (GR, RHOB, NPHI, DT, RES).

`nlp/relation_extractor.py` links entities using two simple, deterministic
scopes:
1. **Document/page level, well-centric**: when exactly one WELL entity is
   present on a page (the common case for a single-well report whose
   attributes are spread across label/value lines), it's linked to every
   LICENCE/COMPANY/FORMATION/FIELD/PRODUCTION entity on that page.
2. **Line level**: FORMATION -> DEPTH pairing (`HAS_TOP_DEPTH`/
   `HAS_BASE_DEPTH`), since formation-tops tables are row-scoped regardless
   of well count. Keyword triggers ("top"/"base") are used when present;
   otherwise a plain two-depth table row is read as (top, base) by
   convention.

This is intentionally not full coreference resolution -- with multiple
wells on a page, the extractor falls back to precise same-line/sentence
co-occurrence with keyword triggers instead of guessing.

## 6. Normalization & Entity Resolution

`normalization/name_normalizer.py` and `unit_normalizer.py` handle casing,
suffix-stripping, unit conversion (km/cm/ft -> meters) and multi-format date
parsing -- all deterministic, never raising on bad input.

`normalization/entity_resolver.py` resolves WELL/LICENCE/COMPANY/FIELD
entities against the reference tables using a conservative tiered strategy:
**exact match** on the normalized name, then a **conservative fuzzy match**
(rapidfuzz, default threshold 92/100) as a last resort. Anything below
threshold is left `UNRESOLVED` and surfaces as a validation warning rather
than being silently guessed.

## 7. Database

**`migrations/001_init_reference_schema.sql`** creates a small,
explicitly-labeled **stand-in** for the real SODIR/Volve normalized
schema -- `ref_companies`, `ref_licences`, `ref_fields`, `ref_wells` --
seeded with a handful of demo rows (well `30/6-1`, licence `PL 123`,
operator `Equinor`, field `Volve`) so entity resolution has real canonical
IDs to resolve against. **This is not a reproduction of the SODIR
factpages or Volve dataset schema** and must be replaced with the real
normalized tables before any production use.

**`migrations/002_init_ingestion_schema.sql`** creates the pipeline's own
tables: `ingestion_runs`, `documents`, `document_pages`, `document_chunks`
(with a `vector(384)` column + ivfflat cosine index), `extracted_entities`
(with nullable FKs into each `ref_*` table), `extracted_relations`, and
`validation_results`.

Migrations are plain SQL (not `Base.metadata.create_all()`, since
`CREATE EXTENSION vector` and seed data don't map cleanly to SQLAlchemy
DDL) applied via `scripts/apply_migrations.py`, tracked in a
`schema_migrations` bookkeeping table. `ingestion/storage/models.py`
mirrors the same tables as SQLAlchemy ORM models for application code.

## 8. pgvector Storage

`storage/vector_writer.py` inserts `Chunk.embedding` values into
`document_chunks.embedding` and exposes a `similarity_search()` helper
using pgvector's cosine-distance operator, provided for reuse by a future
LangGraph QA workflow (not wired into this ingestion CLI).

## 9. LangGraph Workflow

`graph/workflow.py` builds a small `StateGraph`:

```
detect_source -> load_document -> extract_text -(needs_ocr?)-> ocr_fallback
    -> clean_text -> extract_entities -> extract_relations -> normalize
    -> resolve_entities -> validate -(fatal_error?)-> persist -> chunk
    -> embed -> store_vectors -> END
```

Every node catches its own exceptions: fatal issues (document totally
unreadable) append to `state["errors"]` and set `fatal_error`, routing
straight to `END`; recoverable issues (OCR unavailable, an entity that
didn't resolve, a page that failed to parse) append to
`state["warnings"]` and the graph continues. There are two Postgres commit
points -- after `persist` and after `store_vectors` -- so a vector-storage
failure never rolls back already-persisted entities/relations.

## 10. Chunking & Embeddings

`chunking/chunker.py` splits each page's cleaned text into section-aware
chunks when heading-like lines are detected, falling back to a fixed-size
(~1200 char) sliding window with ~150 char overlap otherwise.
`embeddings/sentence_transformer_embedder.py` uses a local
`sentence-transformers` model (`all-MiniLM-L6-v2`, 384-dim) -- no API key,
no network dependency once the model is cached locally.

## 11. Environment Setup Notes (macOS)

Two machine-specific quirks were hit while setting this up on this machine
(macOS 26.2, very new at the time) and are worth knowing if you recreate
`.venv`:

1. **`pip` bootstrap fails via `ensurepip`** on this Python 3.12 build with
   a `platform.mac_ver()` / truststore `ValueError`, because
   `platform.mac_ver()` returns an empty string on this OS version. Worked
   around by adding a `.pth` file to `site-packages` that patches
   `platform.mac_ver` to fall back to a non-empty string, then bootstrapping
   pip by downloading a wheel and extracting it directly rather than via
   `ensurepip`/`get-pip.py` (which hit a second, apparently-unrelated pip
   self-install bug).
2. **`import pyexpat` fails to `dlopen`** (`Symbol not found:
   _XML_SetAllocTrackerActivationThreshold`) because this Python build's
   `pyexpat` extension is linked against `/usr/lib/libexpat.1.dylib`, and
   this OS version's system libexpat is older than what it expects. Fixed
   by running with `DYLD_LIBRARY_PATH=/opt/homebrew/opt/expat/lib` (a
   newer Homebrew-installed `expat`) so pip's own dependencies import
   correctly.

If `pip install -r requirements.txt` fails outright on a fresh machine,
these two issues are the first thing to check; on an older/more common
macOS version neither should be necessary.

## 12. CLI Usage

```
python -m ingestion.pipeline --input path/to/document.pdf
python -m ingestion.pipeline --input path/to/documents/ --source text
```

Prints a summary (documents/pages processed, entity counts by type,
relations, resolved/unresolved, chunks/embeddings created, warnings,
errors) and exits non-zero only if the run status is `FAILED`.

## 13. Configuration

All configuration is via environment variables (see `.env.example`):
`DATABASE_URL`, `TEST_DATABASE_URL`, `EMBEDDING_MODEL`, `OCR_ENABLED`,
`OCR_LANGUAGE`, `CHUNK_SIZE`, `CHUNK_OVERLAP`, `FUZZY_MATCH_THRESHOLD`,
`LOG_LEVEL`. Importing the package never requires a live database
connection; `DATABASE_URL` is only validated when a DB operation is
actually attempted, and the pipeline degrades gracefully (with a warning,
not a crash) when it's unset.

## 14. Testing

Run `pytest`. Pure-Python unit tests (extraction, normalization,
validation, chunking) require no setup. DB-backed tests (entity
resolution, Postgres/vector writers, the end-to-end test) read
`TEST_DATABASE_URL` and are skipped automatically if it's unset. Tests
that exercise the full LangGraph workflow are marked `@pytest.mark.slow`
since they trigger a real (local) embedding model call; run
`pytest -m "not slow"` for a fast subset.

To run the DB-backed tests:

```
createdb sihpipeline_test   # or point TEST_DATABASE_URL at an existing DB
export TEST_DATABASE_URL=postgresql+psycopg2://localhost:5432/sihpipeline_test
pytest
```

## 15. Known Limitations & Future Production Improvements

This is a **demo/MVP**, not a production system. Known gaps:

- **Reference schema is a stand-in.** `ref_*` tables are a hand-seeded
  substitute for the real SODIR/Volve normalized schema and must be
  replaced before production use.
- **No full coreference resolution.** Relation extraction uses page-level
  and line-level heuristics, not a real coreference model; multi-well
  documents fall back to precise (but less complete) same-line matching.
- **Entity coverage is partial.** LITHOLOGY, RESERVOIR, PRESSURE,
  DRILLING_EVENT, COMPLETION, DEPTH_INTERVAL, DISCOVERY and WELLBORE are
  defined in the ontology but don't yet have dedicated extractors.
- **No trained NER/relation model.** Purely regex/dictionary-based --
  works well for the structured vocabulary it knows about, will miss
  novel phrasings.
- **No reranking, no hybrid retrieval, no QA workflow.** This package only
  covers ingestion; a future LangGraph QA workflow would consume
  `document_chunks`/`extracted_entities` but isn't built here.
- **Single-process, single-document-at-a-time.** No queues, no distributed
  workers, no batch optimization beyond a simple directory loop in the CLI.
- **Python version.** The project venv uses Python 3.12 (not 3.14, which was
  the initial environment's default) since 3.14 was too new for `pip`
  itself to bootstrap reliably at the time this was built. Recreate `.venv`
  with `python3.12 -m venv .venv` if you see wheel/build issues on a newer
  interpreter.

Production hardening would include: replacing the reference schema with
real SODIR/Volve data, adding a trained/fine-tuned NER+relation model (or
an LLM-based extractor) with human-in-the-loop review of low-confidence
extractions, proper coreference resolution, batch/async processing,
observability (metrics/tracing, not just an `ingestion_runs` table), and a
real migration framework (Alembic) instead of hand-numbered SQL files.
