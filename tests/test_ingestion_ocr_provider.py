import io
import shutil

import pytest
from PIL import Image, ImageDraw

from ingestion.config import get_settings
from ingestion.ocr.tesseract_provider import TesseractOCRProvider


def _blank_image_bytes() -> bytes:
    img = Image.new("RGB", (200, 60), color="white")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def test_ocr_disabled_returns_error_without_raising(monkeypatch):
    monkeypatch.setenv("OCR_ENABLED", "false")
    get_settings.cache_clear()
    try:
        provider = TesseractOCRProvider()
        result = provider.extract_text(_blank_image_bytes(), page=1)
        assert result.text == ""
        assert result.error is not None
    finally:
        monkeypatch.delenv("OCR_ENABLED", raising=False)
        get_settings.cache_clear()


def test_missing_tesseract_binary_fails_gracefully(monkeypatch):
    import pytesseract

    def _raise(*args, **kwargs):
        raise pytesseract.TesseractNotFoundError()

    monkeypatch.setattr(pytesseract, "image_to_data", _raise)
    provider = TesseractOCRProvider()
    result = provider.extract_text(_blank_image_bytes(), page=1)
    assert result.text == ""
    assert result.confidence == 0.0
    assert result.error is not None


@pytest.mark.skipif(shutil.which("tesseract") is None, reason="tesseract binary not installed")
def test_ocr_happy_path_extracts_text():
    img = Image.new("RGB", (300, 80), color="white")
    draw = ImageDraw.Draw(img)
    draw.text((10, 20), "HELLO WORLD", fill="black")
    buf = io.BytesIO()
    img.save(buf, format="PNG")

    provider = TesseractOCRProvider()
    result = provider.extract_text(buf.getvalue(), page=1)
    assert result.error is None
    assert "HELLO" in result.text.upper()
