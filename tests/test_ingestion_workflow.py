import pytest
from PIL import Image

from ingestion.config import get_settings
from ingestion.graph.workflow import build_graph
from tests.conftest import SAMPLE_WELL_REPORT


@pytest.fixture()
def no_ingestion_database(monkeypatch):
    monkeypatch.delenv("INGESTION_DATABASE_URL", raising=False)
    monkeypatch.delenv("DATABASE_URL", raising=False)
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.mark.slow
def test_text_input_skips_ocr_branch(no_ingestion_database):
    graph = build_graph()
    final_state = graph.invoke({
        "input_path": str(SAMPLE_WELL_REPORT), "source_override": None,
        "errors": [], "warnings": [],
    })
    assert final_state.get("fatal_error") is not True
    assert final_state.get("needs_ocr") is False
    assert len(final_state.get("entities", [])) > 0
    assert not any("OCR" in w for w in final_state.get("warnings", []))
    assert any("DATABASE_URL" in w for w in final_state.get("warnings", []))
    assert final_state.get("errors", []) == []


@pytest.mark.slow
def test_image_input_forces_ocr_branch_and_degrades_gracefully(tmp_path, monkeypatch, no_ingestion_database):
    monkeypatch.setenv("OCR_ENABLED", "false")
    get_settings.cache_clear()

    img = Image.new("RGB", (100, 40), color="white")
    path = tmp_path / "scan.png"
    img.save(path)

    graph = build_graph()
    final_state = graph.invoke({
        "input_path": str(path), "source_override": None,
        "errors": [], "warnings": [],
    })
    assert final_state.get("needs_ocr") is True
    assert any("OCR" in w for w in final_state.get("warnings", []))
    assert final_state.get("errors", []) == []

    monkeypatch.delenv("OCR_ENABLED", raising=False)
    get_settings.cache_clear()


def test_missing_file_is_fatal_but_does_not_raise(no_ingestion_database):
    graph = build_graph()
    final_state = graph.invoke({
        "input_path": "/nonexistent/path/does_not_exist.txt", "source_override": None,
        "errors": [], "warnings": [],
    })
    assert final_state.get("fatal_error") is True
    assert len(final_state.get("errors", [])) > 0
