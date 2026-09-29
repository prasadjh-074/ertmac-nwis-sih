"""Handwriting detection — page-level and region-level.

Combines multiple heuristic signals (OCR confidence, word geometry,
stroke characteristics, line regularity) into a weighted classification.

Detection is independent of handwriting OCR: a page can be classified
as HANDWRITTEN even when no handwriting OCR provider is available.
"""

from __future__ import annotations

import io
import logging
from typing import Optional

from .heuristics import (
    analyze_line_regularity,
    analyze_ocr_confidence,
    analyze_stroke_characteristics,
    analyze_word_geometry,
)
from .models import (
    ContentClassification,
    HandwritingDetection,
    HandwritingOCRStatus,
    HandwritingRegion,
)

logger = logging.getLogger(__name__)

# Weighted combination of heuristic signals.
# OCR confidence is the strongest signal (it's always available when
# OCR ran); stroke and geometry provide cross-validation.
_WEIGHTS = {
    "ocr_confidence": 0.35,
    "word_geometry": 0.20,
    "stroke": 0.25,
    "line_regularity": 0.20,
}

# Classification thresholds on the combined [0,1] score.
# >0.6 → HANDWRITTEN, <0.3 → TYPED, in between → MIXED.
# These are deliberately conservative — false positives (claiming
# handwriting that's actually typed) are worse than false negatives.
HANDWRITTEN_THRESHOLD = 0.60
TYPED_THRESHOLD = 0.30
MIN_CONFIDENCE_FOR_CLASSIFICATION = 0.25


def detect_page(
    image_bytes: bytes,
    ocr_data: Optional[dict] = None,
    page_number: int = 1,
    *,
    handwritten_threshold: float = HANDWRITTEN_THRESHOLD,
    typed_threshold: float = TYPED_THRESHOLD,
) -> HandwritingDetection:
    """Detect whether a page contains typed, handwritten, or mixed content.

    Args:
        image_bytes: Raw image bytes (PNG/JPEG) of the page.
        ocr_data: Tesseract image_to_data output dict.  If None, only
                  image-based heuristics are used.
        page_number: 1-indexed page number.
        handwritten_threshold: Score above which content is classified
                               as HANDWRITTEN.
        typed_threshold: Score below which content is classified as TYPED.

    Returns:
        HandwritingDetection with classification, confidence, and features.
    """
    features = {}
    scores = {}
    available_weights = {}

    # 1. OCR confidence analysis
    if ocr_data and ocr_data.get("text"):
        ocr_result = analyze_ocr_confidence(ocr_data)
        features["ocr_confidence"] = ocr_result
        if ocr_result["signal"] != "insufficient_data":
            scores["ocr_confidence"] = ocr_result["handwriting_score"]
            available_weights["ocr_confidence"] = _WEIGHTS["ocr_confidence"]

    # 2. Word geometry analysis
    if ocr_data:
        geo_result = analyze_word_geometry(ocr_data)
        features["word_geometry"] = geo_result
        if geo_result["signal"] != "insufficient_data":
            scores["word_geometry"] = geo_result["geometry_score"]
            available_weights["word_geometry"] = _WEIGHTS["word_geometry"]

    # 3. Stroke characteristics (image-based)
    if image_bytes:
        stroke_result = analyze_stroke_characteristics(image_bytes)
        features["stroke"] = stroke_result
        if stroke_result["signal"] not in ("unavailable", "error", "insufficient_ink",
                                            "blank_or_sparse", "non_text"):
            scores["stroke"] = stroke_result["stroke_score"]
            available_weights["stroke"] = _WEIGHTS["stroke"]

    # 4. Line regularity
    if ocr_data:
        line_result = analyze_line_regularity(ocr_data)
        features["line_regularity"] = line_result
        if line_result["signal"] != "insufficient_lines":
            scores["line_regularity"] = line_result["line_score"]
            available_weights["line_regularity"] = _WEIGHTS["line_regularity"]

    # Combine scores with available weights
    if not scores:
        return HandwritingDetection(
            page_number=page_number,
            classification=ContentClassification.UNKNOWN,
            confidence=0.0,
            detection_method="heuristic_ensemble",
            features=features,
        )

    total_weight = sum(available_weights.values())
    combined_score = sum(
        scores[k] * available_weights[k] / total_weight
        for k in scores
    )

    # Confidence based on how many signals agree
    signal_agreement = _compute_agreement(scores)
    confidence = min(1.0, signal_agreement * (len(scores) / len(_WEIGHTS)))

    # Classify
    if combined_score >= handwritten_threshold:
        classification = ContentClassification.HANDWRITTEN
        handwritten_frac = combined_score
        typed_frac = 1.0 - combined_score
    elif combined_score <= typed_threshold:
        classification = ContentClassification.TYPED
        handwritten_frac = combined_score
        typed_frac = 1.0 - combined_score
    elif confidence < MIN_CONFIDENCE_FOR_CLASSIFICATION:
        classification = ContentClassification.UNKNOWN
        handwritten_frac = combined_score
        typed_frac = 1.0 - combined_score
    else:
        classification = ContentClassification.MIXED
        handwritten_frac = combined_score
        typed_frac = 1.0 - combined_score

    needs_hw_ocr = classification in (
        ContentClassification.HANDWRITTEN,
        ContentClassification.MIXED,
    )

    ocr_status = HandwritingOCRStatus.NOT_NEEDED
    if needs_hw_ocr:
        ocr_status = HandwritingOCRStatus.DETECTED_OCR_UNAVAILABLE

    return HandwritingDetection(
        page_number=page_number,
        classification=classification,
        confidence=round(confidence, 3),
        detection_method="heuristic_ensemble",
        handwritten_fraction=round(handwritten_frac, 3),
        typed_fraction=round(typed_frac, 3),
        needs_handwriting_ocr=needs_hw_ocr,
        ocr_status=ocr_status,
        features=features,
    )


def detect_regions(
    image_bytes: bytes,
    ocr_data: dict,
    page_number: int = 1,
    *,
    min_region_words: int = 3,
) -> list[HandwritingRegion]:
    """Detect handwritten regions within a mixed page.

    Splits the page into vertical bands based on OCR word positions
    and classifies each band independently.  Returns regions where
    the classification differs from the page majority.

    This is a coarse localization — not pixel-perfect.
    """
    text_list = ocr_data.get("text", [])
    conf_list = ocr_data.get("conf", [])
    top_list = ocr_data.get("top", [])
    left_list = ocr_data.get("left", [])
    width_list = ocr_data.get("width", [])
    height_list = ocr_data.get("height", [])

    if len(text_list) < min_region_words * 2:
        return []

    # Group words into vertical bands (roughly line groups)
    words = []
    for i in range(len(text_list)):
        word = str(text_list[i]).strip()
        if not word:
            continue
        conf = conf_list[i] if i < len(conf_list) else -1
        if conf in ("-1", -1):
            continue
        if i < len(top_list) and i < len(left_list) and i < len(width_list) and i < len(height_list):
            words.append({
                "conf": float(conf),
                "top": int(top_list[i]),
                "left": int(left_list[i]),
                "width": int(width_list[i]),
                "height": int(height_list[i]),
            })

    if len(words) < min_region_words * 2:
        return []

    # Sort by vertical position
    words.sort(key=lambda w: w["top"])

    # Split into bands of ~10 words
    band_size = max(min_region_words, len(words) // 6)
    bands = [words[i:i + band_size] for i in range(0, len(words), band_size)]

    # Get the page-level majority classification from overall mean confidence
    all_confs = [w["conf"] for w in words]
    page_mean = sum(all_confs) / len(all_confs)
    page_is_typed = page_mean > 60

    regions = []
    region_id = 0

    # Get image dimensions for area fraction
    try:
        from PIL import Image
        img = Image.open(io.BytesIO(image_bytes))
        img_area = img.size[0] * img.size[1]
    except Exception:
        img_area = 1

    for band in bands:
        if len(band) < min_region_words:
            continue

        band_confs = [w["conf"] for w in band]
        band_mean = sum(band_confs) / len(band_confs)

        # Only report regions that differ from page majority
        band_is_typed = band_mean > 60
        if band_is_typed == page_is_typed:
            continue

        region_id += 1
        x = min(w["left"] for w in band)
        y = min(w["top"] for w in band)
        x2 = max(w["left"] + w["width"] for w in band)
        y2 = max(w["top"] + w["height"] for w in band)
        region_area = (x2 - x) * (y2 - y)

        classification = ContentClassification.TYPED if band_is_typed else ContentClassification.HANDWRITTEN
        confidence = abs(band_mean - 60) / 40.0
        confidence = min(1.0, max(0.0, confidence))

        regions.append(HandwritingRegion(
            region_id=region_id,
            bbox=(x, y, x2 - x, y2 - y),
            classification=classification,
            confidence=round(confidence, 3),
            area_fraction=round(region_area / img_area, 3) if img_area > 1 else 0.0,
        ))

    return regions


def _compute_agreement(scores: dict[str, float]) -> float:
    """Measure how much the heuristic signals agree (0=conflicting, 1=unanimous)."""
    if len(scores) <= 1:
        return 0.7  # single signal, moderate confidence

    values = list(scores.values())
    mean = sum(values) / len(values)
    variance = sum((v - mean) ** 2 for v in values) / len(values)
    # Low variance = high agreement
    agreement = max(0.0, 1.0 - variance * 4)
    return agreement
