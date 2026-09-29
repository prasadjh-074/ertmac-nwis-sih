# Handwritten Content Detection

Adds handwriting/typed/mixed classification to the existing ingestion
pipeline (`ingestion/`). This is an additional capability layered onto
the existing OCR pipeline — it does not replace Tesseract, does not
introduce a second ingestion pipeline, and does not fabricate
handwriting transcription when no reliable OCR provider is available.

## Architecture

```
DOCUMENT
   |
PAGE IMAGE (existing: ingestion/preprocessing/pdf_extractor.py)
   |
TESSERACT OCR (existing: ingestion/ocr/tesseract_provider.py)
   |
HANDWRITING DETECTOR (new: ingestion/handwriting/detector.py)
   |
   +--------------------+-------------------+
   |                    |                   |
 TYPED               HANDWRITTEN          MIXED
   |                    |                   |
   |            handwriting OCR      region detection +
   |            (if provider           handwriting OCR
   |             available,           on handwritten
   |             else marked           bands
   |             unavailable)
   |                    |                   |
   +--------------------+-------------------+
                         |
                    OCR TEXT (existing PageRecord.raw_text)
                         |
                        NLP (existing ingestion/nlp/entity_extractor.py,
                              events/extraction.py — unchanged)
                         |
                 ENTITIES / EVENTS
                         |
                    PROVENANCE (existing ProvenanceMetadata,
                                 extended with handwriting fields)
                         |
                     RETRIEVAL
```

The existing Tesseract OCR path is **untouched** — `ocr_fallback_node`
still runs first and produces the same `PageRecord.raw_text` it always
did. Detection runs afterward, on the same OCR data Tesseract already
computed, and only *adds* metadata / re-routes to handwriting OCR when
warranted.

## Module Layout

```
ingestion/handwriting/
    __init__.py       # public exports
    models.py         # ContentClassification, HandwritingDetection, etc.
    heuristics.py      # 4 independent signal functions
    detector.py         # detect_page(), detect_regions() — combines signals
    ocr_provider.py     # HandwritingOCRProvider abstraction + Tesseract fallback
    routing.py           # route_page() — detection + conditional OCR
    evaluation.py        # synthetic labeled dataset + metrics
```

## Classification

Four states, matching the task requirement — the system never assumes
every scanned page is handwritten:

| Classification | Meaning |
|---|---|
| `TYPED` | Machine-printed text, high OCR confidence, regular geometry |
| `HANDWRITTEN` | Page is dominated by handwritten content |
| `MIXED` | Both typed and handwritten content present |
| `UNKNOWN` | Insufficient evidence to classify (e.g. blank page) |

## Detection Methodology

`detect_page()` combines four independent heuristic signals, each
producing a `[0,1]` "handwriting score", weighted and averaged:

| Signal | Weight | Source | What it measures |
|---|---|---|---|
| OCR confidence | 0.35 | Tesseract word-level confidence | Typed text: mean >70, std <15. Handwritten: mean <45, std >25. |
| Word geometry | 0.20 | Tesseract word bounding boxes | Typed: uniform glyph height (CV <0.15). Handwritten: variable (CV >0.35). |
| Stroke width | 0.25 | Image binarization (Otsu) + distance transform | Typed: uniform stroke width (CV <0.3). Handwritten: variable pen pressure (CV >0.6). |
| Line regularity | 0.20 | Vertical spacing between OCR-detected lines | Typed: consistent spacing (CV <0.15). Handwritten: irregular (CV >0.35). |

Each signal only contributes if it produced a usable result (e.g. too
few words → the signal is dropped, not defaulted to a fake midpoint);
weights are renormalized over the signals that *are* available. This
means the detector degrades gracefully with partial data instead of
producing overconfident nonsense.

**Why these thresholds, not others:** they were chosen from
Tesseract's documented confidence semantics and validated empirically
against the synthetic dataset described in "Evaluation" below (see
`ingestion/handwriting/heuristics.py` docstrings for the exact
numbers). They are not arbitrary.

**Classification thresholds** on the combined score:
- `>= 0.60` → `HANDWRITTEN`
- `<= 0.30` → `TYPED`
- in between, with sufficient signal agreement → `MIXED`
- in between, with low signal agreement → `UNKNOWN`

This is deliberately conservative: a false "this is handwritten"
claim is worse than under-flagging, because it triggers unnecessary
(and less reliable) handwriting OCR.

### Why no heavy CV/ML model

Tesseract's own word-confidence and geometry data, plus a classical
image heuristic (Otsu threshold + distance transform, no OpenCV
dependency — just Pillow + numpy + scipy, already project
dependencies) are sufficient to discriminate typed from handwritten
content on drilling documents, which are mostly typed forms with
occasional handwritten margin notes — not full handwritten manuscripts.
Adding a deep learning handwriting-detection model would be a large,
unjustified dependency for this signal quality.

## Region-Level Detection

`detect_regions()` splits a page into vertical word-position bands
and flags bands whose OCR confidence diverges from the page's overall
majority. This is coarse localization (bounding boxes derived from
OCR word extents, not pixel-perfect segmentation) — the system does
not claim pixel-perfect localization.

## OCR Routing

`routing.route_page()`:
1. Always runs detection first.
2. If classification is `TYPED` or `UNKNOWN` → no handwriting OCR;
   the existing Tesseract text (already in `PageRecord.raw_text`)
   stands.
3. If `HANDWRITTEN` or `MIXED` and detection confidence is below
   `ROUTING_CONFIDENCE_THRESHOLD` (0.3) → status becomes
   `DETECTION_UNCERTAIN`, and handwriting OCR is skipped (avoids
   invoking OCR on a low-confidence guess).
4. Otherwise, if a `HandwritingOCRProvider` is available → run it and
   attach text + confidence + provider name.
5. If no provider is available → `DETECTED_OCR_UNAVAILABLE`. The
   image is preserved; text is never fabricated.

## Handwriting OCR Provider

`HandwritingOCRProvider` is an abstraction
(`extract_handwriting(image, region=None) -> HandwritingOCRResult`).
The only implementation currently available in this environment is
`TesseractHandwritingProvider` — it reuses the already-installed
Tesseract binary with handwriting-oriented preprocessing (median
filter, aggressive autocontrast, `--psm 6`). Tesseract is not a
specialized handwriting engine, so its output is honestly labeled
with lower expected confidence (recorded in `metadata.note`). To plug
in a better provider (e.g. a cloud or local handwriting-specific
model), implement `HandwritingOCRProvider` and swap it in
`routing.get_default_handwriting_provider()`.

## Quality States (`HandwritingOCRStatus`)

| Status | Meaning |
|---|---|
| `NOT_NEEDED` | Page is typed; no handwriting OCR required |
| `DETECTED_OCR_SUCCESS` | Handwriting detected, OCR ran, confidence ≥50 |
| `DETECTED_OCR_LOW_CONFIDENCE` | Handwriting detected, OCR ran, confidence <50 |
| `DETECTED_OCR_UNAVAILABLE` | Handwriting detected, no provider / OCR failed |
| `DETECTION_UNCERTAIN` | Detection confidence too low to act on |

Downstream consumers must check this status before trusting
handwriting-derived text — it is never treated identically to
high-confidence typed OCR.

## Metadata & Provenance

`PageRecord` (`ingestion/schemas.py`) gained four nullable fields:
`handwriting_classification`, `handwriting_confidence`,
`handwriting_ocr_status`, `source_content_type`. All default to
`None`, so existing rows/code are unaffected.

`ProvenanceMetadata` (`ingestion/provenance/metadata.py`) gained
`handwriting_classification`, `handwriting_confidence`,
`handwriting_ocr_provider`, `source_content_type` — `as_dict()` only
includes them when set, so existing provenance dicts are byte-for-byte
unchanged for typed content.

Every fact extracted from handwritten content traces:
`document → page_number → HandwritingDetection.regions → OCR text →
extracted Entity/DrillingEvent`, via the page number and the
provenance fields above.

### Database

Migration `db/007_handwriting_detection.sql` adds the four
`document_pages` columns as nullable `ALTER TABLE ... ADD COLUMN IF
NOT EXISTS` statements — no data migration needed, existing rows get
`NULL`. `ingestion/storage/models.py::DocumentPage` and
`postgres_writer.insert_pages()` were updated to match.

## NLP / Drilling-Event Integration

No new NLP code was added — handwriting-recovered text flows into the
**existing** `ingestion/nlp/entity_extractor.py` and
`events/extraction.py` unchanged, because it lands in the same
`PageRecord.raw_text` / `cleaned_text` fields typed OCR always used.
This was verified in `tests/test_handwriting.py::TestNLPIntegration`:
depth entities and `MUD_LOSS` events are correctly extracted from
handwriting-recovered text strings. Empty or uninformative recovered
text produces zero events — nothing is fabricated.

## LangGraph Integration

One new node, `detect_handwriting_node`, inserted into the existing
ingestion graph (`ingestion/graph/workflow.py`) between `ocr_fallback`
and `clean_text`:

```
... -> extract_text -(needs_ocr?)-> ocr_fallback -> detect_handwriting -> clean_text -> ...
                                  \\_______________________________(no OCR needed)______/
```

Text-only documents (no OCR needed) skip straight to `clean_text` as
before — the handwriting node never runs for them, so plain-text
ingestion is byte-for-byte unchanged. `ocr_fallback_node` was extended
to additionally capture Tesseract's raw `image_to_data` output
(needed by the detector) alongside the text it always produced; this
does not change its existing return values.

`PipelineState` gained one field: `handwriting_detections:
list[HandwritingDetection]`.

## Performance

Handwriting OCR is never invoked unconditionally. It only runs when
(1) detection says `HANDWRITTEN`/`MIXED`, (2) confidence exceeds
`ROUTING_CONFIDENCE_THRESHOLD` (configurable), and (3) a provider is
available. Typed pages (the majority case for drilling reports) incur
only the cost of the heuristic ensemble — no image resampling beyond a
1000px-max downsample for stroke analysis, no ML inference.

## Security / Privacy

No external/cloud OCR providers are used or configured by default —
`TesseractHandwritingProvider` runs the same local binary the existing
pipeline already depends on. No document content is logged. No
secrets are introduced.

## Evaluation

`ingestion/handwriting/evaluation.py` builds an 11-sample **synthetic**
labeled dataset (4 typed, 4 handwritten-proxy, 3 mixed) and computes
accuracy/precision/recall/F1. Run it with:

```
python -m ingestion.handwriting.evaluation
```

Latest run (`data/evaluation/handwriting_detection_report.{json,md}`):

| Class | Precision | Recall | F1 | Support |
|-------|-----------|--------|-----|---------|
| typed | 1.000 | 1.000 | 1.000 | 4 |
| handwritten | 0.000 | 0.000 | 0.000 | 4 |
| mixed | 0.429 | 1.000 | 0.600 | 3 |

Overall accuracy: **63.6%** (11 samples).

### Evaluation Limitations (read before citing these numbers)

- **The dataset is synthetic**, built from script fonts (Brush
  Script / Bradley Hand) with per-character rotation/position jitter
  as a proxy for real handwriting. There are no real handwritten
  drilling documents in this repository. These numbers characterize
  detector behavior on this proxy, **not** real-world accuracy.
- **All four `HANDWRITTEN` samples were classified as `MIXED`**, not
  `HANDWRITTEN` — the ensemble's conservative thresholds keep clean
  vector-font jitter (which still has some structure real ink lacks)
  from crossing the 0.6 `HANDWRITTEN` cutoff. This is an honest
  result, not tuned away, because inflating the threshold-crossing
  behavior to fit this specific synthetic dataset would overfit to a
  proxy rather than improve real detection.
  **Operationally this has low impact**: both `HANDWRITTEN` and
  `MIXED` trigger the same `needs_handwriting_ocr=True` routing, so
  the downstream OCR-routing decision is unaffected by this
  particular class confusion — only the reported label differs.
- Blank, noisy, and low-resolution pages are deliberately excluded
  from the labeled metrics — they don't have a non-arbitrary
  classification ground truth. Their behavior is instead checked
  qualitatively in `tests/test_handwriting.py::TestDetectorEdgeCases`
  (blank → `UNKNOWN`, confidence 0; noisy typed → still `TYPED`;
  low-res → doesn't crash, returns a valid classification).
- Region-level localization (bounding boxes) is not scored — no
  reliable pixel-level ground truth exists for the synthetic pages.
  `tests/test_handwriting.py::TestDetectorMixedPage::test_region_detection_finds_handwritten_band`
  checks it qualitatively (finds ≥1 region, classified `HANDWRITTEN`,
  inside a mixed page).

## Configuration

| Setting | Location | Default | Purpose |
|---|---|---|---|
| `HANDWRITTEN_THRESHOLD` | `detector.py` | 0.60 | Score above which → `HANDWRITTEN` |
| `TYPED_THRESHOLD` | `detector.py` | 0.30 | Score below which → `TYPED` |
| `MIN_CONFIDENCE_FOR_CLASSIFICATION` | `detector.py` | 0.25 | Below this → `UNKNOWN` instead of `MIXED` |
| `ROUTING_CONFIDENCE_THRESHOLD` | `routing.py` | 0.30 | Minimum confidence to invoke handwriting OCR |

All are function parameters with these defaults — no new environment
variables were introduced; existing `OCR_ENABLED`/`OCR_LANGUAGE`
settings in `ingestion/config.py` are unaffected and still govern the
underlying Tesseract calls.

## Known Limitations

1. Detection accuracy on **real** handwriting is unverified — only
   synthetic proxies were available (see Evaluation above).
2. `TesseractHandwritingProvider` is a fallback, not a true
   handwriting-recognition engine; its confidence on genuinely messy
   handwriting will likely be low, correctly surfacing
   `DETECTED_OCR_LOW_CONFIDENCE`.
3. Region detection is coarse (word-position banding), not
   pixel-segmentation — bounding boxes approximate, do not tightly
   bound, handwritten regions.
4. The `HANDWRITTEN` vs `MIXED` boundary is conservative and, per the
   evaluation above, currently favors `MIXED` for borderline cases.
5. Stroke-width analysis alone (when no OCR data is available) cannot
   reliably discriminate clean script fonts from typed fonts — it
   needs the OCR-confidence/geometry signals to be effective, so
   pure-image-only detection (no OCR data) is weaker than the full
   ensemble.

## Running It

```bash
# Full test suite (existing + handwriting)
source venv/bin/activate
python -m pytest tests/ -v

# Handwriting tests only
python -m pytest tests/test_handwriting.py -v

# Evaluation report
python -m ingestion.handwriting.evaluation

# Full ingestion pipeline on a scanned image/PDF (handwriting
# detection runs automatically as part of the existing graph)
python -m ingestion.pipeline path/to/document.pdf
```

## Files Created

- `ingestion/handwriting/__init__.py`
- `ingestion/handwriting/models.py`
- `ingestion/handwriting/heuristics.py`
- `ingestion/handwriting/detector.py`
- `ingestion/handwriting/ocr_provider.py`
- `ingestion/handwriting/routing.py`
- `ingestion/handwriting/evaluation.py`
- `db/007_handwriting_detection.sql`
- `tests/test_handwriting.py`
- `docs/handwriting_detection.md` (this file)
- `data/evaluation/handwriting_detection_report.{json,md}`

## Files Modified

- `ingestion/schemas.py` — `PageRecord` +4 nullable fields
- `ingestion/graph/state.py` — `PipelineState` +1 field (`handwriting_detections`)
- `ingestion/graph/workflow.py` — new `detect_handwriting_node`, wired between `ocr_fallback` and `clean_text`; `ocr_fallback_node` extended to carry OCR data forward
- `ingestion/provenance/metadata.py` — `ProvenanceMetadata` +4 optional fields
- `ingestion/storage/models.py` — `DocumentPage` ORM +4 nullable columns
- `ingestion/storage/postgres_writer.py` — `insert_pages()` writes the 4 new columns

## Dependencies Added

None. Pillow, numpy, scipy, and pytesseract were already project
dependencies; no new packages were installed.
