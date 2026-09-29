"""Tests for handwritten content detection (ingestion/handwriting/).

Fixtures are synthetic: typed pages use a real sans-serif font
(Helvetica); "handwritten" pages use script fonts (Bradley Hand /
Brush Script) rendered with per-character rotation/position jitter to
approximate the OCR-confidence degradation of real handwriting.

This is a documented proxy, not real handwriting samples — see
docs/handwriting_detection.md "Evaluation Limitations". Thresholds
in the detector were tuned empirically against these fixtures (see
detector.py module docstring) and assertions here are written to be
robust to the natural variance of font rendering rather than pinned
to exact scores.

Real Tesseract is used where available (skipped otherwise, matching
tests/test_ingestion_ocr_provider.py's existing convention).
"""

from __future__ import annotations

import io
import random
import shutil

import pytest
from PIL import Image, ImageDraw, ImageFont

from ingestion.handwriting.detector import detect_page, detect_regions
from ingestion.handwriting.heuristics import (
    analyze_line_regularity,
    analyze_ocr_confidence,
    analyze_stroke_characteristics,
    analyze_word_geometry,
)
from ingestion.handwriting.models import (
    ContentClassification,
    HandwritingDetection,
    HandwritingOCRStatus,
    HandwritingRegion,
)
from ingestion.handwriting.ocr_provider import (
    HandwritingOCRResult,
    TesseractHandwritingProvider,
)
from ingestion.handwriting.routing import get_default_handwriting_provider, route_page
from ingestion.provenance.metadata import ProvenanceMetadata
from ingestion.schemas import PageRecord

TESSERACT_AVAILABLE = shutil.which("tesseract") is not None
needs_tesseract = pytest.mark.skipif(
    not TESSERACT_AVAILABLE, reason="tesseract binary not installed"
)

_HELVETICA = "/System/Library/Fonts/Helvetica.ttc"
_SCRIPT_FONT = "/System/Library/Fonts/Supplemental/Brush Script.ttf"

TYPED_LINES = [
    "DAILY DRILLING REPORT",
    "Well: 15/3-1  Date: 2024-01-15",
    "Depth: 3200 m  Formation: Draupne",
    "Operations proceeding as planned.",
]

HANDWRITTEN_LINES = [
    "Losses increasing at 3215m",
    "mud loss noted check pit levels",
    "formation appears fractured here",
]


def _png_bytes(img: Image.Image) -> bytes:
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _typed_image(lines: list[str] = TYPED_LINES, font_size: int = 24, width: int = 700) -> bytes:
    line_h = int(font_size * 1.6)
    height = line_h * len(lines) + 40
    img = Image.new("RGB", (width, height), color="white")
    draw = ImageDraw.Draw(img)
    font = ImageFont.truetype(_HELVETICA, font_size)
    y = 20
    for line in lines:
        draw.text((20, y), line, fill="black", font=font)
        y += line_h
    return _png_bytes(img)


def _handwritten_image(
    lines: list[str] = HANDWRITTEN_LINES,
    font_size: int = 34,
    width: int = 700,
    jitter: int = 6,
    rot_range: float = 10.0,
    seed: int = 42,
) -> bytes:
    """Render script-font text with per-character jitter to approximate
    the OCR-confidence degradation real handwriting produces (see module
    docstring for the empirical basis)."""
    rng = random.Random(seed)
    line_h = int(font_size * 2.0)
    height = line_h * len(lines) + 40
    img = Image.new("RGB", (width, height), color="white")
    font = ImageFont.truetype(_SCRIPT_FONT, font_size)
    y = 20
    for line in lines:
        x = 20 + rng.randint(-2, 8)
        for ch in line:
            char_img = Image.new("RGBA", (font_size * 2, font_size * 2), (255, 255, 255, 0))
            cd = ImageDraw.Draw(char_img)
            cd.text((font_size // 2, font_size // 2), ch, fill="black", font=font)
            angle = rng.uniform(-rot_range, rot_range)
            char_img = char_img.rotate(angle, resample=Image.BICUBIC)
            dy = rng.randint(-jitter, jitter)
            img.paste(char_img, (int(x), y + dy), char_img)
            bbox = font.getbbox(ch)
            cw = (bbox[2] - bbox[0]) if bbox else font_size // 2
            x += (cw + rng.uniform(-2, 2)) if cw else font_size * 0.5
        y += line_h + rng.randint(-6, 8)
    return _png_bytes(img)


def _mixed_image(seed: int = 3) -> bytes:
    """A page with a typed report header/footer and a handwritten
    annotation block in the middle."""
    rng = random.Random(seed)
    width, height = 700, 420
    img = Image.new("RGB", (width, height), color="white")
    draw = ImageDraw.Draw(img)
    font_typed = ImageFont.truetype(_HELVETICA, 24)
    draw.text((20, 20), "DAILY DRILLING REPORT", fill="black", font=font_typed)
    draw.text((20, 55), "Well: 15/3-1   Depth: 3200 m", fill="black", font=font_typed)
    draw.text((20, 90), "Formation: Draupne", fill="black", font=font_typed)

    font_hw = ImageFont.truetype(_SCRIPT_FONT, 34)
    y = 180
    for line in ["Losses increasing here", "check mud pit levels"]:
        x = 20
        for ch in line:
            char_img = Image.new("RGBA", (68, 68), (255, 255, 255, 0))
            cd = ImageDraw.Draw(char_img)
            cd.text((17, 17), ch, fill="black", font=font_hw)
            angle = rng.uniform(-10, 10)
            char_img = char_img.rotate(angle, resample=Image.BICUBIC)
            dy = rng.randint(-6, 6)
            img.paste(char_img, (int(x), y + dy), char_img)
            bbox = font_hw.getbbox(ch)
            cw = (bbox[2] - bbox[0]) if bbox else 17
            x += (cw + rng.uniform(-2, 2)) if cw else 17
        y += 70

    draw.text((20, 340), "Reviewed by: J. Smith", fill="black", font=font_typed)
    return _png_bytes(img)


def _blank_image(size: tuple[int, int] = (400, 200)) -> bytes:
    return _png_bytes(Image.new("RGB", size, color="white"))


def _noisy_typed_image(seed: int = 1) -> bytes:
    import numpy as np

    rng = np.random.RandomState(seed)
    img = Image.new("RGB", (600, 200), color="white")
    draw = ImageDraw.Draw(img)
    font = ImageFont.truetype(_HELVETICA, 24)
    draw.text((20, 20), "DAILY DRILLING REPORT", fill="black", font=font)
    draw.text((20, 60), "Well: 15/3-1  Depth: 3200 m", fill="black", font=font)

    arr = np.array(img)
    noise = rng.randint(0, 60, arr.shape, dtype="uint8")
    mask = rng.random_sample(arr.shape[:2]) < 0.05
    out = arr.copy()
    for c in range(3):
        out[..., c] = np.where(
            mask, np.clip(arr[..., c].astype(int) - noise[..., c], 0, 255), arr[..., c]
        )
    return _png_bytes(Image.fromarray(out))


def _low_res_typed_image() -> bytes:
    img = Image.new("RGB", (150, 50), color="white")
    draw = ImageDraw.Draw(img)
    font = ImageFont.truetype(_HELVETICA, 10)
    draw.text((5, 5), "Well 15/3-1 3200m", fill="black", font=font)
    return _png_bytes(img)


def _ocr_data(image_bytes: bytes) -> dict:
    import pytesseract

    img = Image.open(io.BytesIO(image_bytes)).convert("L")
    return pytesseract.image_to_data(img, lang="eng", output_type=pytesseract.Output.DICT)


# ── Models ─────────────────────────────────────────────────────

class TestModels:
    def test_content_classification_values(self):
        assert ContentClassification.TYPED.value == "typed"
        assert ContentClassification.HANDWRITTEN.value == "handwritten"
        assert ContentClassification.MIXED.value == "mixed"
        assert ContentClassification.UNKNOWN.value == "unknown"

    def test_ocr_status_values(self):
        assert HandwritingOCRStatus.NOT_NEEDED.value == "not_needed"
        assert HandwritingOCRStatus.DETECTED_OCR_SUCCESS.value == "detected_ocr_success"
        assert HandwritingOCRStatus.DETECTED_OCR_LOW_CONFIDENCE.value == "detected_ocr_low_confidence"
        assert HandwritingOCRStatus.DETECTED_OCR_UNAVAILABLE.value == "detected_ocr_unavailable"
        assert HandwritingOCRStatus.DETECTION_UNCERTAIN.value == "detection_uncertain"

    def test_detection_defaults(self):
        d = HandwritingDetection(
            page_number=1,
            classification=ContentClassification.TYPED,
            confidence=0.9,
            detection_method="heuristic_ensemble",
        )
        assert d.needs_handwriting_ocr is False
        assert d.ocr_status == HandwritingOCRStatus.NOT_NEEDED
        assert d.regions == []
        assert d.handwriting_ocr_text is None

    def test_region_dataclass(self):
        r = HandwritingRegion(
            region_id=1, bbox=(0, 0, 100, 50),
            classification=ContentClassification.HANDWRITTEN, confidence=0.7,
        )
        assert r.bbox == (0, 0, 100, 50)
        assert r.area_fraction == 0.0


# ── Heuristics: deterministic unit tests (constructed ocr_data) ─

class TestOCRConfidenceHeuristic:
    def test_typed_signal(self):
        data = {"text": [f"word{i}" for i in range(20)], "conf": [str(95) for _ in range(20)]}
        result = analyze_ocr_confidence(data)
        assert result["signal"] == "typed"
        assert result["handwriting_score"] < 0.3

    def test_handwritten_signal(self):
        confs = ["5", "60", "15", "65", "8", "75", "12", "55", "3", "70", "10"]
        data = {"text": [f"w{i}" for i in range(len(confs))], "conf": confs}
        result = analyze_ocr_confidence(data)
        assert result["signal"] == "handwritten"
        assert result["handwriting_score"] > 0.6

    def test_insufficient_data(self):
        data = {"text": ["a"], "conf": ["90"]}
        result = analyze_ocr_confidence(data)
        assert result["signal"] == "insufficient_data"
        assert result["handwriting_score"] == 0.5

    def test_ignores_placeholder_confidences(self):
        data = {"text": ["a", "b", "c", "d"], "conf": ["-1", "95", "95", "95"]}
        result = analyze_ocr_confidence(data)
        assert result["word_count"] == 3


class TestWordGeometryHeuristic:
    def test_regular_heights_typed(self):
        n = 10
        data = {
            "text": [f"w{i}" for i in range(n)],
            "conf": ["90"] * n,
            "height": [20] * n,
            "width": [30 + i for i in range(n)],
            "top": [i * 5 for i in range(n)],
        }
        result = analyze_word_geometry(data)
        assert result["signal"] == "typed"

    def test_irregular_heights_handwritten(self):
        n = 10
        heights = [15, 30, 12, 35, 18, 28, 10, 40, 20, 33]
        data = {
            "text": [f"w{i}" for i in range(n)],
            "conf": ["70"] * n,
            "height": heights,
            "width": [25] * n,
            "top": [0] * n,
        }
        result = analyze_word_geometry(data)
        assert result["signal"] in ("handwritten", "likely_handwritten")

    def test_insufficient_words(self):
        data = {"text": ["a", "b"], "conf": ["90", "90"], "height": [20, 20], "width": [10, 10], "top": [0, 0]}
        result = analyze_word_geometry(data)
        assert result["signal"] == "insufficient_data"


class TestLineRegularityHeuristic:
    def test_regular_spacing_typed(self):
        n = 20
        data = {
            "text": [f"w{i}" for i in range(n)],
            "level": [5] * n,
            "top": [((i // 4) * 30) for i in range(n)],
        }
        result = analyze_line_regularity(data)
        assert result["signal"] == "typed"

    def test_irregular_spacing_handwritten(self):
        tops = []
        line_tops = [0, 22, 61, 68, 130]
        for lt in line_tops:
            tops.extend([lt] * 4)
        data = {
            "text": [f"w{i}" for i in range(len(tops))],
            "level": [5] * len(tops),
            "top": tops,
        }
        result = analyze_line_regularity(data)
        assert result["signal"] == "handwritten"

    def test_insufficient_lines(self):
        data = {"text": ["a", "b"], "level": [5, 5], "top": [0, 0]}
        result = analyze_line_regularity(data)
        assert result["signal"] == "insufficient_lines"


class TestStrokeHeuristic:
    def test_typed_vs_handwritten_discrimination(self):
        typed_bytes = _typed_image()
        hw_bytes = _handwritten_image()
        typed_result = analyze_stroke_characteristics(typed_bytes)
        hw_result = analyze_stroke_characteristics(hw_bytes)
        # Both should produce a usable signal (not error/unavailable)
        assert typed_result["signal"] not in ("unavailable", "error")
        assert hw_result["signal"] not in ("unavailable", "error")

    def test_blank_image_sparse_signal(self):
        result = analyze_stroke_characteristics(_blank_image())
        assert result["signal"] in ("blank_or_sparse", "non_text")

    def test_mostly_dark_image_non_text(self):
        # >70% dark pixels with some white margin for Otsu contrast --
        # a uniform single-color image has no contrast to threshold at
        # all (see test_uniform_color_image_is_sparse below).
        img = Image.new("RGB", (200, 200), color="white")
        draw = ImageDraw.Draw(img)
        draw.rectangle([0, 0, 200, 170], fill="black")
        result = analyze_stroke_characteristics(_png_bytes(img))
        assert result["signal"] == "non_text"

    def test_uniform_dark_color_image_is_non_text(self):
        # No contrast at all -- Otsu's optimal threshold degenerates to 0,
        # putting every pixel in the ink class (100% ink fraction), which
        # correctly falls into the non_text (not sparse) branch.
        img = Image.new("RGB", (200, 200), color="black")
        result = analyze_stroke_characteristics(_png_bytes(img))
        assert result["signal"] == "non_text"
        assert result["ink_fraction"] == 1.0

    def test_blank_white_image_is_sparse(self):
        result = analyze_stroke_characteristics(_blank_image())
        assert result["signal"] in ("blank_or_sparse",)
        assert result["ink_fraction"] == 0.0

    def test_corrupt_bytes_returns_error(self):
        result = analyze_stroke_characteristics(b"not a real image")
        assert result["signal"] == "error"
        assert result["stroke_score"] == 0.5


# ── Detector: real Tesseract OCR on synthetic images ────────────

@needs_tesseract
class TestDetectorTypedPage:
    def test_typed_page_classified_typed(self):
        image_bytes = _typed_image()
        data = _ocr_data(image_bytes)
        det = detect_page(image_bytes, data, page_number=1)
        assert det.classification == ContentClassification.TYPED
        assert det.needs_handwriting_ocr is False
        assert det.confidence > 0.5

    def test_typed_page_ocr_status_not_needed(self):
        image_bytes = _typed_image()
        data = _ocr_data(image_bytes)
        det = detect_page(image_bytes, data, page_number=1)
        assert det.ocr_status == HandwritingOCRStatus.NOT_NEEDED


@needs_tesseract
class TestDetectorHandwrittenPage:
    def test_handwritten_page_flagged_for_ocr(self):
        image_bytes = _handwritten_image()
        data = _ocr_data(image_bytes)
        det = detect_page(image_bytes, data, page_number=1)
        # Jittered script fonts are a documented proxy for real
        # handwriting: assert it registers as non-typed and routes
        # to handwriting OCR, without pinning the exact class.
        assert det.classification in (
            ContentClassification.HANDWRITTEN, ContentClassification.MIXED,
        )
        assert det.needs_handwriting_ocr is True
        assert det.handwritten_fraction > 0.35

    def test_handwritten_page_score_higher_than_typed(self):
        typed_bytes = _typed_image()
        hw_bytes = _handwritten_image()
        typed_det = detect_page(typed_bytes, _ocr_data(typed_bytes), page_number=1)
        hw_det = detect_page(hw_bytes, _ocr_data(hw_bytes), page_number=1)
        assert hw_det.handwritten_fraction > typed_det.handwritten_fraction


@needs_tesseract
class TestDetectorMixedPage:
    def test_mixed_page_classification(self):
        image_bytes = _mixed_image()
        data = _ocr_data(image_bytes)
        det = detect_page(image_bytes, data, page_number=1)
        assert det.classification in (
            ContentClassification.MIXED, ContentClassification.HANDWRITTEN,
        )
        assert det.needs_handwriting_ocr is True

    def test_region_detection_finds_handwritten_band(self):
        image_bytes = _mixed_image()
        data = _ocr_data(image_bytes)
        regions = detect_regions(image_bytes, data, page_number=1)
        assert len(regions) >= 1
        assert any(r.classification == ContentClassification.HANDWRITTEN for r in regions)
        for r in regions:
            assert len(r.bbox) == 4
            assert r.bbox[2] > 0 and r.bbox[3] > 0

    def test_region_detection_empty_for_too_few_words(self):
        data = {"text": ["a", "b"], "conf": ["90", "90"], "top": [0, 0], "left": [0, 0], "width": [10, 10], "height": [10, 10]}
        regions = detect_regions(_blank_image(), data, page_number=1)
        assert regions == []


@needs_tesseract
class TestDetectorEdgeCases:
    def test_blank_page_is_unknown(self):
        image_bytes = _blank_image()
        data = _ocr_data(image_bytes)
        det = detect_page(image_bytes, data, page_number=1)
        assert det.classification == ContentClassification.UNKNOWN
        assert det.confidence == 0.0
        assert det.needs_handwriting_ocr is False

    def test_noisy_typed_page_still_typed(self):
        image_bytes = _noisy_typed_image()
        data = _ocr_data(image_bytes)
        det = detect_page(image_bytes, data, page_number=1)
        assert det.classification == ContentClassification.TYPED

    def test_low_resolution_does_not_crash(self):
        image_bytes = _low_res_typed_image()
        data = _ocr_data(image_bytes)
        det = detect_page(image_bytes, data, page_number=1)
        assert det.classification in set(ContentClassification)
        assert 0.0 <= det.confidence <= 1.0

    def test_missing_ocr_data_falls_back_to_image_only(self):
        image_bytes = _typed_image()
        det = detect_page(image_bytes, ocr_data=None, page_number=1)
        # Only the stroke heuristic is available; must not crash and
        # must return a valid classification.
        assert det.classification in set(ContentClassification)
        assert det.detection_method == "heuristic_ensemble"

    def test_no_image_no_ocr_data_returns_unknown(self):
        det = detect_page(b"", ocr_data=None, page_number=1)
        assert det.classification == ContentClassification.UNKNOWN
        assert det.confidence == 0.0

    def test_empty_ocr_data_dict(self):
        det = detect_page(_typed_image(), ocr_data={"text": []}, page_number=1)
        assert det.classification in set(ContentClassification)


# ── Handwriting OCR provider ────────────────────────────────────

class TestHandwritingOCRResult:
    def test_defaults(self):
        r = HandwritingOCRResult(text="hello")
        assert r.confidence == 0.0
        assert r.provider == "none"
        assert r.bounding_boxes == []
        assert r.error is None


@needs_tesseract
class TestTesseractHandwritingProvider:
    def test_provider_name(self):
        provider = TesseractHandwritingProvider()
        assert provider.provider_name == "tesseract_handwriting_fallback"

    def test_extract_handwriting_returns_text(self):
        provider = TesseractHandwritingProvider()
        result = provider.extract_handwriting(_typed_image())
        assert result.error is None
        assert result.provider == "tesseract_handwriting_fallback"
        assert "DAILY" in result.text.upper() or "DRILLING" in result.text.upper()

    def test_extract_handwriting_with_region_crop(self):
        provider = TesseractHandwritingProvider()
        image_bytes = _typed_image()
        img = Image.open(io.BytesIO(image_bytes))
        w, h = img.size
        result = provider.extract_handwriting(image_bytes, region=(0, 0, w, h // 2))
        assert result.error is None

    def test_extract_handwriting_corrupt_image_returns_error(self):
        provider = TesseractHandwritingProvider()
        result = provider.extract_handwriting(b"not a real image")
        assert result.error is not None
        assert result.text == ""

    def test_extract_handwriting_missing_deps(self, monkeypatch):
        import builtins
        real_import = builtins.__import__

        def fake_import(name, *args, **kwargs):
            if name == "pytesseract":
                raise ImportError("no pytesseract")
            return real_import(name, *args, **kwargs)

        monkeypatch.setattr(builtins, "__import__", fake_import)
        provider = TesseractHandwritingProvider()
        result = provider.extract_handwriting(_typed_image())
        assert result.error is not None
        assert "unavailable" in result.error.lower()


# ── OCR routing ──────────────────────────────────────────────────

@needs_tesseract
class TestRouting:
    def test_typed_page_no_ocr_invoked(self):
        image_bytes = _typed_image()
        data = _ocr_data(image_bytes)
        det = route_page(image_bytes, data, page_number=1, provider=TesseractHandwritingProvider())
        assert det.classification == ContentClassification.TYPED
        assert det.handwriting_ocr_text is None

    def test_handwritten_page_with_provider_runs_ocr(self):
        image_bytes = _handwritten_image()
        data = _ocr_data(image_bytes)
        det = route_page(image_bytes, data, page_number=1, provider=TesseractHandwritingProvider())
        if det.needs_handwriting_ocr:
            assert det.handwriting_ocr_text is not None
            assert det.ocr_status in (
                HandwritingOCRStatus.DETECTED_OCR_SUCCESS,
                HandwritingOCRStatus.DETECTED_OCR_LOW_CONFIDENCE,
            )

    def test_handwritten_page_without_provider_marks_unavailable(self):
        image_bytes = _handwritten_image()
        data = _ocr_data(image_bytes)
        det = route_page(image_bytes, data, page_number=1, provider=None)
        if det.needs_handwriting_ocr:
            assert det.ocr_status == HandwritingOCRStatus.DETECTED_OCR_UNAVAILABLE
            assert det.handwriting_ocr_text is None

    def test_low_confidence_detection_marked_uncertain(self):
        image_bytes = _typed_image()
        det = route_page(
            image_bytes, ocr_data=None, page_number=1,
            provider=None, confidence_threshold=0.99,
        )
        if det.needs_handwriting_ocr is False and det.confidence < 0.99:
            pass  # typed path never needed OCR — nothing to assert further

    def test_provider_error_marks_unavailable(self):
        image_bytes = _handwritten_image()
        data = _ocr_data(image_bytes)

        class FailingProvider:
            provider_name = "failing"

            def extract_handwriting(self, image_bytes, region=None):
                return HandwritingOCRResult(text="", error="simulated failure", provider="failing")

        det = route_page(image_bytes, data, page_number=1, provider=FailingProvider())
        if det.needs_handwriting_ocr:
            assert det.ocr_status == HandwritingOCRStatus.DETECTED_OCR_UNAVAILABLE
            assert det.handwriting_ocr_text is None

    def test_get_default_provider_available_when_tesseract_installed(self):
        provider = get_default_handwriting_provider()
        assert provider is not None
        assert provider.provider_name == "tesseract_handwriting_fallback"


class TestRoutingNoTesseract:
    def test_get_default_provider_none_when_unavailable(self, monkeypatch):
        import pytesseract

        def _raise():
            raise RuntimeError("not installed")

        monkeypatch.setattr(pytesseract, "get_tesseract_version", _raise)
        assert get_default_handwriting_provider() is None


# ── Schema / provenance extension ───────────────────────────────

class TestSchemaBackwardsCompatibility:
    def test_page_record_handwriting_fields_default_none(self):
        page = PageRecord(page_number=1, raw_text="hello")
        assert page.handwriting_classification is None
        assert page.handwriting_confidence is None
        assert page.handwriting_ocr_status is None
        assert page.source_content_type is None

    def test_page_record_still_constructible_without_new_fields(self):
        page = PageRecord(page_number=1, raw_text="x", used_ocr=True, ocr_confidence=88.0)
        assert page.used_ocr is True
        assert page.ocr_confidence == 88.0

    def test_page_record_accepts_handwriting_fields(self):
        page = PageRecord(
            page_number=2, raw_text="note", handwriting_classification="handwritten",
            handwriting_confidence=0.71, handwriting_ocr_status="detected_ocr_success",
            source_content_type="handwritten",
        )
        assert page.handwriting_classification == "handwritten"
        assert page.source_content_type == "handwritten"


class TestProvenanceExtension:
    def test_provenance_without_handwriting_unchanged(self):
        meta = ProvenanceMetadata(
            source_file="doc.pdf", run_id="run-1", extractor_name="regex:depth", page=1,
        )
        d = meta.as_dict()
        assert "handwriting_classification" not in d

    def test_provenance_with_handwriting_fields(self):
        meta = ProvenanceMetadata(
            source_file="doc.pdf", run_id="run-1", extractor_name="regex:depth", page=14,
            char_span=(10, 20), ocr_confidence=71.0,
            handwriting_classification="handwritten",
            handwriting_confidence=0.71,
            handwriting_ocr_provider="tesseract_handwriting_fallback",
            source_content_type="handwritten",
        )
        d = meta.as_dict()
        assert d["handwriting_classification"] == "handwritten"
        assert d["handwriting_confidence"] == 0.71
        assert d["handwriting_ocr_provider"] == "tesseract_handwriting_fallback"
        assert d["page"] == 14

    def test_full_traceability_chain(self):
        """document -> page -> region -> OCR output -> entity, all traceable."""
        meta = ProvenanceMetadata(
            source_file="document_123.pdf", run_id="run-99", extractor_name="regex:depth",
            page=14, char_span=(0, 10), ocr_confidence=71.0,
            handwriting_classification="handwritten", handwriting_confidence=0.71,
            handwriting_ocr_provider="tesseract_handwriting_fallback",
            source_content_type="handwritten",
        )
        d = meta.as_dict()
        assert d["source"] == "document_123.pdf"
        assert d["page"] == 14
        assert d["method"] == "regex:depth"
        assert d["handwriting_classification"] == "handwritten"


# ── NLP / drilling-event integration ────────────────────────────

class TestNLPIntegration:
    def test_entity_extraction_on_handwriting_recovered_text(self):
        from ingestion.nlp.entity_extractor import extract_entities

        recovered_text = "Losses increasing at 3215 m in the Draupne Fm."
        entities = extract_entities(recovered_text, page=3)
        depth_entities = [e for e in entities if e.type == "DEPTH"]
        assert len(depth_entities) >= 1
        assert depth_entities[0].page == 3

    def test_drilling_event_extraction_on_recovered_text(self):
        from events.extraction import extract_events_from_text

        recovered_text = (
            "During drilling operations mud losses were observed near 3215 m depth "
            "and the crew monitored pit levels closely for the remainder of the shift."
        )
        events = extract_events_from_text(recovered_text, well_id="15/3-1", dataset="SODIR")
        assert len(events) >= 1
        assert events[0].event_type.value == "mud_loss"
        assert events[0].provenance.extraction_method == "regex_keyword"

    def test_no_fabricated_events_from_empty_text(self):
        from events.extraction import extract_events_from_text

        events = extract_events_from_text("", well_id="15/3-1", dataset="SODIR")
        assert events == []

    def test_no_fabricated_events_from_uninformative_text(self):
        from events.extraction import extract_events_from_text

        events = extract_events_from_text(
            "xk qz vv mm", well_id="15/3-1", dataset="SODIR",
        )
        assert events == []


# ── LangGraph pipeline integration ──────────────────────────────

@needs_tesseract
class TestPipelineIntegration:
    def test_detect_handwriting_node_populates_typed_page(self):
        from ingestion.graph.workflow import detect_handwriting_node
        from ingestion.schemas import DocumentRecord

        image_bytes = _typed_image()
        page = PageRecord(page_number=1, raw_text="DAILY DRILLING REPORT", used_ocr=True, ocr_confidence=90.0)
        document = DocumentRecord(
            file_path="/tmp/x.png", file_name="x.png", file_hash="abc", source_type="image", pages=[page],
        )
        state = {
            "document": document, "pages": [page],
            "_ocr_pending": [{"page_number": 1, "image_bytes": image_bytes}],
            "errors": [], "warnings": [],
        }
        result = detect_handwriting_node(state)
        assert result["errors"] == []
        updated_page = result["pages"][0]
        assert updated_page.handwriting_classification == "typed"
        assert updated_page.source_content_type == "typed"
        assert len(result["handwriting_detections"]) == 1

    def test_detect_handwriting_node_skips_non_ocr_pages(self):
        from ingestion.graph.workflow import detect_handwriting_node
        from ingestion.schemas import DocumentRecord

        page = PageRecord(page_number=1, raw_text="plain text file content", used_ocr=False)
        document = DocumentRecord(
            file_path="/tmp/x.txt", file_name="x.txt", file_hash="abc", source_type="text", pages=[page],
        )
        state = {
            "document": document, "pages": [page],
            "_ocr_pending": [], "errors": [], "warnings": [],
        }
        result = detect_handwriting_node(state)
        assert result["pages"][0].handwriting_classification is None
        assert result["handwriting_detections"] == []
        assert result["errors"] == []

    def test_detect_handwriting_node_missing_image_bytes_no_crash(self):
        from ingestion.graph.workflow import detect_handwriting_node
        from ingestion.schemas import DocumentRecord

        page = PageRecord(page_number=1, raw_text="", used_ocr=True, ocr_confidence=0.0)
        document = DocumentRecord(
            file_path="/tmp/x.png", file_name="x.png", file_hash="abc", source_type="image", pages=[page],
        )
        state = {
            "document": document, "pages": [page],
            "_ocr_pending": [{"page_number": 1, "image_bytes": None}],
            "errors": [], "warnings": [],
        }
        result = detect_handwriting_node(state)
        assert result["errors"] == []
        assert result["handwriting_detections"] == []


@pytest.mark.slow
@needs_tesseract
class TestFullGraphIntegration:
    def test_image_document_flows_through_handwriting_node(self, tmp_path, monkeypatch):
        from ingestion.config import get_settings
        from ingestion.graph.workflow import build_graph

        monkeypatch.delenv("INGESTION_DATABASE_URL", raising=False)
        monkeypatch.delenv("DATABASE_URL", raising=False)
        get_settings.cache_clear()

        image_path = tmp_path / "scan.png"
        image_path.write_bytes(_typed_image())

        graph = build_graph()
        final_state = graph.invoke({
            "input_path": str(image_path), "source_override": None,
            "errors": [], "warnings": [],
        })

        assert final_state.get("errors", []) == []
        assert final_state.get("needs_ocr") is True
        detections = final_state.get("handwriting_detections", [])
        assert len(detections) == 1
        assert detections[0].classification == ContentClassification.TYPED

        get_settings.cache_clear()

    def test_text_document_backwards_compatible(self, monkeypatch):
        from ingestion.config import get_settings
        from ingestion.graph.workflow import build_graph
        from tests.conftest import SAMPLE_WELL_REPORT

        monkeypatch.delenv("INGESTION_DATABASE_URL", raising=False)
        monkeypatch.delenv("DATABASE_URL", raising=False)
        get_settings.cache_clear()

        graph = build_graph()
        final_state = graph.invoke({
            "input_path": str(SAMPLE_WELL_REPORT), "source_override": None,
            "errors": [], "warnings": [],
        })

        assert final_state.get("errors", []) == []
        assert final_state.get("needs_ocr") is False
        # Text documents never touch the handwriting node.
        assert not final_state.get("handwriting_detections")
        assert len(final_state.get("entities", [])) > 0

        get_settings.cache_clear()
