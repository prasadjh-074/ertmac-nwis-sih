"""Image-based heuristics for handwriting detection.

Uses Pillow + numpy (no OpenCV dependency).  Each heuristic returns a
signal dict that the detector aggregates.

Thresholds are documented with rationale.  All are configurable via
the functions' parameters so tests and future tuning don't require
code changes.
"""

from __future__ import annotations

import io
import logging
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)


def analyze_ocr_confidence(
    ocr_data: dict,
    *,
    typed_mean_threshold: float = 70.0,
    handwritten_mean_threshold: float = 45.0,
    typed_std_threshold: float = 15.0,
    handwritten_std_threshold: float = 25.0,
) -> dict[str, Any]:
    """Analyze Tesseract word-level confidence for handwriting signals.

    Typed text: high mean confidence (>70), low variance (<15 std).
    Handwritten text: low mean confidence (<45), high variance (>25 std).

    Thresholds derived from Tesseract documentation and empirical
    observation on mixed drilling documents.
    """
    confidences = [
        float(c) for c in ocr_data.get("conf", [])
        if c not in ("-1", -1) and float(c) > 0
    ]

    if len(confidences) < 3:
        return {
            "mean_confidence": 0.0,
            "std_confidence": 0.0,
            "word_count": len(confidences),
            "signal": "insufficient_data",
            "handwriting_score": 0.5,
        }

    mean_conf = float(np.mean(confidences))
    std_conf = float(np.std(confidences))
    low_conf_fraction = sum(1 for c in confidences if c < 50) / len(confidences)

    if mean_conf >= typed_mean_threshold and std_conf <= typed_std_threshold:
        signal = "typed"
        hw_score = max(0.0, 0.2 - (mean_conf - typed_mean_threshold) / 100.0)
    elif mean_conf <= handwritten_mean_threshold and std_conf >= handwritten_std_threshold:
        signal = "handwritten"
        hw_score = min(1.0, 0.8 + (handwritten_std_threshold - mean_conf) / 100.0)
    elif low_conf_fraction > 0.5:
        signal = "likely_handwritten"
        hw_score = 0.6 + 0.2 * low_conf_fraction
    elif mean_conf < 60:
        signal = "uncertain_leaning_handwritten"
        hw_score = 0.5 + (60 - mean_conf) / 60.0 * 0.3
    else:
        signal = "likely_typed"
        hw_score = max(0.1, 0.4 - (mean_conf - 60) / 100.0)

    return {
        "mean_confidence": round(mean_conf, 1),
        "std_confidence": round(std_conf, 1),
        "word_count": len(confidences),
        "low_conf_fraction": round(low_conf_fraction, 3),
        "signal": signal,
        "handwriting_score": round(min(1.0, max(0.0, hw_score)), 3),
    }


def analyze_word_geometry(ocr_data: dict) -> dict[str, Any]:
    """Analyze word bounding box geometry for regularity.

    Typed text has consistent word heights and line spacing.
    Handwritten text has variable heights, irregular spacing.
    """
    heights = []
    widths = []
    tops = []

    text_list = ocr_data.get("text", [])
    conf_list = ocr_data.get("conf", [])
    h_list = ocr_data.get("height", [])
    w_list = ocr_data.get("width", [])
    top_list = ocr_data.get("top", [])

    for i in range(len(text_list)):
        word = str(text_list[i]).strip()
        if not word:
            continue
        conf = conf_list[i] if i < len(conf_list) else -1
        if conf in ("-1", -1):
            continue

        if i < len(h_list) and i < len(w_list) and i < len(top_list):
            h = int(h_list[i])
            w = int(w_list[i])
            t = int(top_list[i])
            if h > 0 and w > 0:
                heights.append(h)
                widths.append(w)
                tops.append(t)

    if len(heights) < 5:
        return {
            "height_cv": 0.0,
            "width_cv": 0.0,
            "word_count_geo": len(heights),
            "signal": "insufficient_data",
            "geometry_score": 0.5,
        }

    height_cv = float(np.std(heights) / np.mean(heights)) if np.mean(heights) > 0 else 0
    width_cv = float(np.std(widths) / np.mean(widths)) if np.mean(widths) > 0 else 0

    # Typed text: height CV < 0.15 (very regular font sizes)
    # Handwritten: height CV > 0.3 (variable letter sizes)
    if height_cv < 0.15 and width_cv < 0.8:
        signal = "typed"
        geo_score = 0.1
    elif height_cv > 0.35:
        signal = "handwritten"
        geo_score = 0.8
    elif height_cv > 0.25:
        signal = "likely_handwritten"
        geo_score = 0.6
    else:
        signal = "uncertain"
        geo_score = 0.4

    return {
        "height_cv": round(height_cv, 3),
        "width_cv": round(width_cv, 3),
        "mean_height": round(float(np.mean(heights)), 1),
        "word_count_geo": len(heights),
        "signal": signal,
        "geometry_score": round(geo_score, 3),
    }


def analyze_stroke_characteristics(
    image_bytes: bytes,
    *,
    typed_stroke_cv_threshold: float = 0.3,
    handwritten_stroke_cv_threshold: float = 0.6,
) -> dict[str, Any]:
    """Analyze stroke width variation from a binarized page image.

    Typed text has uniform stroke widths (printed fonts).
    Handwritten text has variable stroke widths (pen pressure).

    Uses distance transform on binarized image to estimate stroke widths.
    """
    try:
        from PIL import Image, ImageOps
        from scipy.ndimage import distance_transform_edt
    except ImportError:
        return {"signal": "unavailable", "stroke_score": 0.5}

    try:
        image = Image.open(io.BytesIO(image_bytes))
        gray = image.convert("L")
        # Downsample for speed (stroke analysis doesn't need full resolution)
        max_dim = 1000
        if max(gray.size) > max_dim:
            ratio = max_dim / max(gray.size)
            gray = gray.resize(
                (int(gray.size[0] * ratio), int(gray.size[1] * ratio)),
                Image.LANCZOS,
            )

        gray = ImageOps.autocontrast(gray)
        arr = np.array(gray)

        # Otsu-like thresholding via numpy
        threshold = _otsu_threshold(arr)
        # <= (not <): Otsu's between-class variance is maximized by the
        # partition {0..t} vs {t+1..255}, so the dark/ink class includes
        # the threshold value itself. With strict "<", a purely bimodal
        # image (e.g. an already-binarized fax-quality scan) can select
        # threshold=0 and then match zero pixels.
        binary = arr <= threshold  # ink pixels = True

        ink_fraction = binary.sum() / binary.size
        if ink_fraction < 0.01 or ink_fraction > 0.7:
            return {
                "ink_fraction": round(float(ink_fraction), 3),
                "signal": "non_text" if ink_fraction > 0.7 else "blank_or_sparse",
                "stroke_score": 0.5,
            }

        # Distance transform gives stroke half-widths
        dt = distance_transform_edt(binary)
        stroke_values = dt[binary]

        if len(stroke_values) < 100:
            return {"signal": "insufficient_ink", "stroke_score": 0.5}

        mean_stroke = float(np.mean(stroke_values))
        std_stroke = float(np.std(stroke_values))
        stroke_cv = std_stroke / mean_stroke if mean_stroke > 0 else 0

        if stroke_cv < typed_stroke_cv_threshold:
            signal = "typed"
            score = 0.1
        elif stroke_cv > handwritten_stroke_cv_threshold:
            signal = "handwritten"
            score = 0.8
        else:
            signal = "uncertain"
            score = 0.3 + (stroke_cv - typed_stroke_cv_threshold) / (
                handwritten_stroke_cv_threshold - typed_stroke_cv_threshold
            ) * 0.4

        return {
            "mean_stroke_width": round(mean_stroke, 2),
            "stroke_cv": round(stroke_cv, 3),
            "ink_fraction": round(float(ink_fraction), 3),
            "signal": signal,
            "stroke_score": round(min(1.0, max(0.0, score)), 3),
        }

    except Exception as exc:
        logger.debug("Stroke analysis failed: %s", exc)
        return {"signal": "error", "stroke_score": 0.5, "error": str(exc)}


def analyze_line_regularity(ocr_data: dict) -> dict[str, Any]:
    """Analyze vertical spacing between text lines.

    Typed text has consistent line spacing.
    Handwritten text has irregular spacing.
    """
    lines: dict[int, list[int]] = {}
    level_list = ocr_data.get("level", [])
    top_list = ocr_data.get("top", [])
    height_list = ocr_data.get("height", [])
    text_list = ocr_data.get("text", [])

    for i in range(len(text_list)):
        word = str(text_list[i]).strip()
        if not word:
            continue
        if i < len(level_list) and i < len(top_list):
            top = int(top_list[i])
            lines.setdefault(top, []).append(i)

    # Cluster nearby tops into lines (within 5px)
    sorted_tops = sorted(lines.keys())
    if len(sorted_tops) < 3:
        return {"line_count": len(sorted_tops), "signal": "insufficient_lines", "line_score": 0.5}

    line_centers = []
    current_cluster = [sorted_tops[0]]
    for t in sorted_tops[1:]:
        if t - current_cluster[-1] < 8:
            current_cluster.append(t)
        else:
            line_centers.append(float(np.mean(current_cluster)))
            current_cluster = [t]
    line_centers.append(float(np.mean(current_cluster)))

    if len(line_centers) < 3:
        return {"line_count": len(line_centers), "signal": "insufficient_lines", "line_score": 0.5}

    spacings = np.diff(line_centers)
    spacing_cv = float(np.std(spacings) / np.mean(spacings)) if np.mean(spacings) > 0 else 0

    # Typed: spacing CV < 0.15
    # Handwritten: spacing CV > 0.35
    if spacing_cv < 0.15:
        signal = "typed"
        score = 0.1
    elif spacing_cv > 0.35:
        signal = "handwritten"
        score = 0.8
    else:
        signal = "uncertain"
        score = 0.3 + (spacing_cv - 0.15) / 0.2 * 0.3

    return {
        "line_count": len(line_centers),
        "spacing_cv": round(spacing_cv, 3),
        "mean_spacing": round(float(np.mean(spacings)), 1),
        "signal": signal,
        "line_score": round(min(1.0, max(0.0, score)), 3),
    }


def _otsu_threshold(image_array: np.ndarray) -> int:
    """Compute Otsu's threshold for a grayscale image array."""
    hist, bin_edges = np.histogram(image_array.ravel(), bins=256, range=(0, 256))
    total = image_array.size
    current_sum = 0.0
    total_sum = float(np.dot(np.arange(256), hist))
    weight_bg = 0
    max_var = 0.0
    threshold = 0

    for t in range(256):
        weight_bg += hist[t]
        if weight_bg == 0:
            continue
        weight_fg = total - weight_bg
        if weight_fg == 0:
            break

        current_sum += t * hist[t]
        mean_bg = current_sum / weight_bg
        mean_fg = (total_sum - current_sum) / weight_fg

        between_var = weight_bg * weight_fg * (mean_bg - mean_fg) ** 2
        if between_var > max_var:
            max_var = between_var
            threshold = t

    return threshold
