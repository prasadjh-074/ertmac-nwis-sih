from ingestion.loaders.source_detector import detect_source


def test_detects_pdf_by_extension(tmp_path):
    p = tmp_path / "report.pdf"
    p.write_bytes(b"%PDF-1.4\n...")
    assert detect_source(str(p)) == "pdf"


def test_detects_text_by_extension(tmp_path):
    p = tmp_path / "notes.txt"
    p.write_text("hello")
    assert detect_source(str(p)) == "text"


def test_detects_image_by_extension(tmp_path):
    p = tmp_path / "scan.png"
    p.write_bytes(b"\x89PNG\r\n\x1a\n" + b"fake")
    assert detect_source(str(p)) == "image"


def test_falls_back_to_magic_bytes_for_unknown_extension(tmp_path):
    p = tmp_path / "mystery.bin"
    p.write_bytes(b"%PDF-1.7\n...")
    assert detect_source(str(p)) == "pdf"


def test_falls_back_to_text_for_plain_content(tmp_path):
    p = tmp_path / "mystery2.bin"
    p.write_bytes(b"just some plain text content")
    assert detect_source(str(p)) == "text"
