from ingestion.preprocessing.text_cleaner import clean_text, join_pages, remove_repeated_lines


def test_merges_hyphenated_line_breaks():
    raw = "This is an exam-\nple of wrapped text."
    assert "example" in clean_text(raw)


def test_collapses_multiple_blank_lines():
    raw = "Para one.\n\n\n\n\nPara two."
    cleaned = clean_text(raw)
    assert "\n\n\n" not in cleaned


def test_collapses_multiple_spaces():
    raw = "Well     30/6-1     Report"
    cleaned = clean_text(raw)
    assert "  " not in cleaned


def test_preserves_line_structure_for_tables():
    raw = "Heimdal    2450 m    2520 m\nSleipner   2520 m    2610 m"
    cleaned = clean_text(raw)
    assert cleaned.count("\n") == 1


def test_fixes_common_ocr_character_mixups():
    raw = "It’s the Heimdal Fm—top depth"
    cleaned = clean_text(raw)
    assert "’" not in cleaned
    assert "—" not in cleaned


def test_remove_repeated_lines_strips_running_header():
    pages = [
        "CONFIDENTIAL REPORT\nPage content one\nfoo",
        "CONFIDENTIAL REPORT\nPage content two\nbar",
        "CONFIDENTIAL REPORT\nPage content three\nbaz",
    ]
    cleaned = remove_repeated_lines(pages)
    assert all("CONFIDENTIAL REPORT" not in p for p in cleaned)
    assert "Page content one" in cleaned[0]


def test_remove_repeated_lines_noop_below_min_pages():
    pages = ["HEADER\nbody one", "HEADER\nbody two"]
    cleaned = remove_repeated_lines(pages, min_page_count=3)
    assert cleaned == pages


def test_join_pages():
    assert join_pages(["a", "b"]) == "a\n\nb"
