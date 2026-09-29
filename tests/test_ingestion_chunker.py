from ingestion.chunking.chunker import chunk_document
from ingestion.schemas import PageRecord


def test_single_short_page_produces_one_chunk():
    page = PageRecord(page_number=1, raw_text="short text", cleaned_text="short text")
    chunks = chunk_document([page], max_chars=1200, overlap=150)
    assert len(chunks) == 1
    assert chunks[0].text == "short text"
    assert chunks[0].page_number == 1


def test_section_aware_split_on_headings():
    text = "Overview\nSome intro text here.\n\nFormation Tops\nHeimdal 2450 m 2520 m"
    page = PageRecord(page_number=1, raw_text=text, cleaned_text=text)
    chunks = chunk_document([page], max_chars=1200, overlap=150)
    sections = {c.section for c in chunks}
    assert "Overview" in sections
    assert "Formation Tops" in sections


def test_fixed_size_fallback_with_overlap():
    long_text = ("word " * 500).strip()
    page = PageRecord(page_number=1, raw_text=long_text, cleaned_text=long_text)
    chunks = chunk_document([page], max_chars=500, overlap=50)
    assert len(chunks) > 1
    for c in chunks:
        assert len(c.text) <= 500 + 1


def test_empty_page_produces_no_chunks():
    page = PageRecord(page_number=1, raw_text="", cleaned_text="")
    chunks = chunk_document([page])
    assert chunks == []


def test_chunk_indices_are_sequential_across_pages():
    page1 = PageRecord(page_number=1, raw_text="first page text", cleaned_text="first page text")
    page2 = PageRecord(page_number=2, raw_text="second page text", cleaned_text="second page text")
    chunks = chunk_document([page1, page2])
    assert [c.chunk_index for c in chunks] == list(range(len(chunks)))
