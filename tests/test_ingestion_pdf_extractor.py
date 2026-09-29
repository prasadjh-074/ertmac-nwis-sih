import pymupdf as fitz
import pytest

from ingestion.preprocessing.pdf_extractor import extract_pdf


def _make_pdf(tmp_path, text_per_page: list[str]) -> str:
    doc = fitz.open()
    for text in text_per_page:
        page = doc.new_page()
        if text:
            page.insert_text((72, 72), text)
    path = tmp_path / "test.pdf"
    doc.save(str(path))
    doc.close()
    return str(path)


def test_extracts_text_from_text_pdf(tmp_path):
    path = _make_pdf(tmp_path, ["Well 30/6-1 report body text here."])
    pages = extract_pdf(path)
    assert len(pages) == 1
    assert pages[0].page_number == 1
    assert "30/6-1" in pages[0].text
    assert pages[0].needs_ocr is False
    assert pages[0].image_bytes is None


def test_flags_blank_page_as_needing_ocr(tmp_path):
    path = _make_pdf(tmp_path, [""])
    pages = extract_pdf(path)
    assert len(pages) == 1
    assert pages[0].needs_ocr is True
    assert pages[0].image_bytes is not None
    assert pages[0].image_bytes.startswith(b"\x89PNG")


def test_multi_page_mixed_content(tmp_path):
    path = _make_pdf(tmp_path, ["Real extractable text on page one that is long enough.", ""])
    pages = extract_pdf(path)
    assert len(pages) == 2
    assert pages[0].needs_ocr is False
    assert pages[1].needs_ocr is True
