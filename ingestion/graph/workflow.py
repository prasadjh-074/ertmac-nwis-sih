"""Small LangGraph ingestion workflow:

detect_source -> load_document -> extract_text -(needs_ocr?)-> ocr_fallback
    -> clean_text -> extract_entities -> extract_relations -> normalize
    -> resolve_entities -> validate -(fatal_error?)-> persist -> chunk
    -> embed -> store_vectors -> END

Every node catches its own exceptions and appends to state["errors"]
(recoverable issues go to state["warnings"] instead) rather than raising --
the graph only short-circuits (validate -> END) on a genuinely fatal
condition (document completely unreadable).
"""
from __future__ import annotations

import logging
import uuid

from langgraph.graph import END, StateGraph

from ingestion.chunking.chunker import chunk_document
from ingestion.config import get_settings
from ingestion.embeddings.sentence_transformer_embedder import SentenceTransformerEmbedder
from ingestion.graph.state import PipelineState
from ingestion.loaders.document_loader import load_document
from ingestion.loaders.source_detector import detect_source
from ingestion.nlp.entity_extractor import extract_entities
from ingestion.nlp.relation_extractor import extract_relations
from ingestion.normalization.name_normalizer import (
    normalize_company_name,
    normalize_formation_name,
    normalize_licence_name,
    normalize_well_name,
)
from ingestion.normalization.unit_normalizer import parse_date, parse_length
from ingestion.ocr.tesseract_provider import TesseractOCRProvider
from ingestion.preprocessing.pdf_extractor import extract_pdf
from ingestion.preprocessing.text_cleaner import clean_text, remove_repeated_lines
from ingestion.schemas import PageRecord
from ingestion.storage import postgres_writer, vector_writer
from ingestion.storage.db import session_scope
from ingestion.validation.validators import validate

logger = logging.getLogger(__name__)


def _lists(state: PipelineState) -> tuple[list[str], list[str]]:
    return list(state.get("errors", [])), list(state.get("warnings", []))


def detect_source_node(state: PipelineState) -> dict:
    errors, warnings = _lists(state)
    try:
        source_type = state.get("source_override") or detect_source(state["input_path"])
        return {"source_type": source_type, "errors": errors, "warnings": warnings}
    except Exception as exc:
        errors.append(f"detect_source: {exc}")
        return {"errors": errors, "warnings": warnings, "fatal_error": True}


def load_document_node(state: PipelineState) -> dict:
    errors, warnings = _lists(state)
    try:
        document = load_document(state["input_path"], state["source_type"])
        return {"document": document, "errors": errors, "warnings": warnings}
    except Exception as exc:
        errors.append(f"load_document: {exc}")
        return {"errors": errors, "warnings": warnings, "fatal_error": True}


def extract_text_node(state: PipelineState) -> dict:
    errors, warnings = _lists(state)
    document = state["document"]
    pages: list[PageRecord] = []
    ocr_pending: list[dict] = []

    try:
        if state["source_type"] == "pdf":
            pdf_pages = extract_pdf(document.file_path)
            for pp in pdf_pages:
                if pp.needs_ocr:
                    pages.append(PageRecord(page_number=pp.page_number, raw_text=""))
                    ocr_pending.append({"page_number": pp.page_number, "image_bytes": pp.image_bytes})
                else:
                    pages.append(PageRecord(page_number=pp.page_number, raw_text=pp.text))
        elif state["source_type"] == "image":
            with open(document.file_path, "rb") as f:
                image_bytes = f.read()
            pages.append(PageRecord(page_number=1, raw_text=""))
            ocr_pending.append({"page_number": 1, "image_bytes": image_bytes})
        else:  # text
            with open(document.file_path, "r", encoding="utf-8", errors="replace") as f:
                text = f.read()
            pages.append(PageRecord(page_number=1, raw_text=text))

        document.pages = pages
        needs_ocr = len(ocr_pending) > 0
        return {
            "document": document, "pages": pages, "needs_ocr": needs_ocr,
            "_ocr_pending": ocr_pending, "errors": errors, "warnings": warnings,
        }
    except Exception as exc:
        errors.append(f"extract_text: {exc}")
        return {"errors": errors, "warnings": warnings, "fatal_error": True}


def ocr_fallback_node(state: PipelineState) -> dict:
    errors, warnings = _lists(state)
    pages: list[PageRecord] = list(state.get("pages", []))
    provider = TesseractOCRProvider()

    ocr_data_by_page: dict[int, dict] = {}

    for pending in state.get("_ocr_pending", []):
        page_number = pending["page_number"]
        image_bytes = pending["image_bytes"]

        # Get full OCR data (not just text) for handwriting detection
        try:
            import io
            import pytesseract
            from PIL import Image, ImageOps

            image = Image.open(io.BytesIO(image_bytes))
            image = image.convert("L")
            image = ImageOps.autocontrast(image)
            data = pytesseract.image_to_data(
                image, lang="eng", output_type=pytesseract.Output.DICT
            )
            ocr_data_by_page[page_number] = data
        except Exception:
            pass

        result = provider.extract_text(image_bytes, page=page_number)
        if result.error:
            warnings.append(
                f"Page {page_number} required OCR but it was unavailable/failed: {result.error}"
            )
            continue
        for i, page in enumerate(pages):
            if page.page_number == page_number:
                pages[i] = PageRecord(
                    page_number=page_number, raw_text=result.text,
                    used_ocr=True, ocr_confidence=result.confidence,
                )
                if result.confidence and result.confidence < 60:
                    warnings.append(
                        f"Page {page_number} OCR confidence is low ({result.confidence:.1f})"
                    )
                break

    document = state["document"]
    document.pages = pages

    # Carry OCR data forward for handwriting detection
    ocr_pending_with_data = []
    for pending in state.get("_ocr_pending", []):
        entry = dict(pending)
        pn = pending["page_number"]
        if pn in ocr_data_by_page:
            entry["ocr_data"] = ocr_data_by_page[pn]
        ocr_pending_with_data.append(entry)

    return {
        "document": document, "pages": pages,
        "_ocr_pending": ocr_pending_with_data,
        "errors": errors, "warnings": warnings,
    }


def detect_handwriting_node(state: PipelineState) -> dict:
    """Detect handwritten content on OCR'd pages.

    Runs between ocr_fallback and clean_text.  Uses Tesseract word-level
    data and image heuristics to classify each page as TYPED, HANDWRITTEN,
    MIXED, or UNKNOWN.  Updates PageRecord metadata accordingly.
    """
    errors, warnings = _lists(state)
    pages: list[PageRecord] = list(state.get("pages", []))
    detections = []

    ocr_pending = state.get("_ocr_pending", [])
    pending_map = {p["page_number"]: p for p in ocr_pending}

    try:
        from ingestion.handwriting.routing import route_page, get_default_handwriting_provider

        hw_provider = get_default_handwriting_provider()

        for i, page in enumerate(pages):
            if not page.used_ocr:
                continue

            pending = pending_map.get(page.page_number)
            if not pending or not pending.get("image_bytes"):
                continue

            image_bytes = pending["image_bytes"]
            ocr_data = pending.get("ocr_data")

            detection = route_page(
                image_bytes, ocr_data, page.page_number,
                provider=hw_provider,
            )
            detections.append(detection)

            pages[i] = PageRecord(
                page_number=page.page_number,
                raw_text=page.raw_text,
                cleaned_text=page.cleaned_text,
                used_ocr=page.used_ocr,
                ocr_confidence=page.ocr_confidence,
                handwriting_classification=detection.classification.value,
                handwriting_confidence=detection.confidence,
                handwriting_ocr_status=detection.ocr_status.value,
                source_content_type=detection.classification.value,
            )

            # If handwriting OCR produced text, append/replace
            if detection.handwriting_ocr_text and detection.ocr_status.value in (
                "detected_ocr_success", "detected_ocr_low_confidence"
            ):
                if detection.classification.value == "handwritten":
                    pages[i].raw_text = detection.handwriting_ocr_text
                elif detection.classification.value == "mixed" and detection.handwriting_ocr_text:
                    if pages[i].raw_text:
                        pages[i].raw_text += "\n[HANDWRITTEN] " + detection.handwriting_ocr_text
                    else:
                        pages[i].raw_text = detection.handwriting_ocr_text

            if detection.classification.value in ("handwritten", "mixed"):
                warnings.append(
                    f"Page {page.page_number}: {detection.classification.value} content detected "
                    f"(confidence: {detection.confidence:.2f}, OCR status: {detection.ocr_status.value})"
                )

    except ImportError as exc:
        warnings.append(f"Handwriting detection unavailable: {exc}")
    except Exception as exc:
        errors.append(f"detect_handwriting: {exc}")

    document = state["document"]
    document.pages = pages
    return {
        "document": document, "pages": pages,
        "handwriting_detections": detections,
        "errors": errors, "warnings": warnings,
    }


def clean_text_node(state: PipelineState) -> dict:
    errors, warnings = _lists(state)
    pages: list[PageRecord] = list(state.get("pages", []))
    try:
        raw_texts = [p.raw_text for p in pages]
        deheadered = remove_repeated_lines(raw_texts)
        cleaned_pages = []
        for page, text in zip(pages, deheadered):
            cleaned_pages.append(PageRecord(
                page_number=page.page_number, raw_text=page.raw_text,
                cleaned_text=clean_text(text), used_ocr=page.used_ocr,
                ocr_confidence=page.ocr_confidence,
            ))
        document = state["document"]
        document.pages = cleaned_pages
        return {"document": document, "pages": cleaned_pages, "errors": errors, "warnings": warnings}
    except Exception as exc:
        errors.append(f"clean_text: {exc}")
        return {"errors": errors, "warnings": warnings}


def extract_entities_node(state: PipelineState) -> dict:
    errors, warnings = _lists(state)
    entities = []
    try:
        for page in state.get("pages", []):
            entities.extend(extract_entities(page.cleaned_text or "", page=page.page_number))
        return {"entities": entities, "errors": errors, "warnings": warnings}
    except Exception as exc:
        errors.append(f"extract_entities: {exc}")
        return {"entities": entities, "errors": errors, "warnings": warnings}


def extract_relations_node(state: PipelineState) -> dict:
    errors, warnings = _lists(state)
    relations = []
    try:
        entities = state.get("entities", [])
        for page in state.get("pages", []):
            page_entities = [e for e in entities if e.page == page.page_number]
            relations.extend(
                extract_relations(page.cleaned_text or "", page_entities, page=page.page_number)
            )
        return {"relations": relations, "errors": errors, "warnings": warnings}
    except Exception as exc:
        errors.append(f"extract_relations: {exc}")
        return {"relations": relations, "errors": errors, "warnings": warnings}


def normalize_node(state: PipelineState) -> dict:
    errors, warnings = _lists(state)
    entities = state.get("entities", [])
    try:
        for entity in entities:
            if entity.type == "WELL":
                entity.normalized_value = normalize_well_name(entity.text)
            elif entity.type == "LICENCE":
                entity.normalized_value = normalize_licence_name(entity.text)
            elif entity.type == "FORMATION" and not entity.normalized_value:
                entity.normalized_value = normalize_formation_name(entity.text)
            elif entity.type == "COMPANY" and not entity.normalized_value:
                entity.normalized_value = normalize_company_name(entity.text)
            elif entity.type == "DEPTH":
                meters = parse_length(entity.text)
                if meters is not None:
                    entity.normalized_value = f"{meters} m"
            elif entity.type == "DATE":
                iso_date = parse_date(entity.text)
                if iso_date is not None:
                    entity.normalized_value = iso_date
        return {"entities": entities, "errors": errors, "warnings": warnings}
    except Exception as exc:
        errors.append(f"normalize: {exc}")
        return {"entities": entities, "errors": errors, "warnings": warnings}


def resolve_entities_node(state: PipelineState) -> dict:
    errors, warnings = _lists(state)
    entities = state.get("entities", [])
    settings = get_settings()

    if not settings.database_url:
        warnings.append("DATABASE_URL not configured -- skipping entity resolution")
        return {"entities": entities, "errors": errors, "warnings": warnings}

    from ingestion.normalization.entity_resolver import (
        resolve_company,
        resolve_field,
        resolve_licence,
        resolve_well,
    )

    resolvers = {
        "WELL": resolve_well, "LICENCE": resolve_licence,
        "COMPANY": resolve_company, "FIELD": resolve_field,
    }

    try:
        with session_scope() as session:
            for entity in entities:
                resolver = resolvers.get(entity.type)
                if resolver is None:
                    continue
                resolved = resolver(session, entity.normalized_value or entity.text)
                if resolved is not None:
                    entity.resolution_status = "RESOLVED"
                    entity.resolved_id = resolved.id
                    entity.resolved_table = resolved.table
    except Exception as exc:
        errors.append(f"resolve_entities: {exc}")

    return {"entities": entities, "errors": errors, "warnings": warnings}


def validate_node(state: PipelineState) -> dict:
    errors, warnings = _lists(state)
    entities = state.get("entities", [])
    relations = state.get("relations", [])
    pages = state.get("pages", [])

    try:
        results = validate(entities, relations)
    except Exception as exc:
        errors.append(f"validate: {exc}")
        results = []

    has_any_text = any((p.cleaned_text or p.raw_text or "").strip() for p in pages)
    fatal_error = not has_any_text

    return {
        "validation_results": results, "errors": errors, "warnings": warnings,
        "fatal_error": fatal_error,
    }


def persist_node(state: PipelineState) -> dict:
    errors, warnings = _lists(state)
    settings = get_settings()

    if not settings.database_url:
        warnings.append("DATABASE_URL not configured -- skipping persistence")
        return {"errors": errors, "warnings": warnings}

    try:
        with session_scope() as session:
            run_id = state.get("db_run_id")
            run = postgres_writer.create_ingestion_run(session, state["input_path"], state["source_type"])
            document_row = postgres_writer.get_or_create_document(session, run.run_id, state["document"])
            postgres_writer.insert_pages(session, document_row.document_id, state.get("pages", []))
            id_map = postgres_writer.insert_entities(
                session, document_row.document_id, run.run_id, state.get("entities", [])
            )
            postgres_writer.insert_relations(
                session, document_row.document_id, run.run_id, state.get("relations", []), id_map
            )
            postgres_writer.insert_validation_results(
                session, run.run_id, document_row.document_id, state.get("validation_results", [])
            )
            db_run_id = str(run.run_id)
            db_document_id = str(document_row.document_id)
        return {
            "db_run_id": db_run_id, "db_document_id": db_document_id,
            "errors": errors, "warnings": warnings,
        }
    except Exception as exc:
        errors.append(f"persist: {exc}")
        return {"errors": errors, "warnings": warnings}


def chunk_node(state: PipelineState) -> dict:
    errors, warnings = _lists(state)
    settings = get_settings()
    try:
        chunks = chunk_document(
            state.get("pages", []), max_chars=settings.chunk_size, overlap=settings.chunk_overlap
        )
        return {"chunks": chunks, "errors": errors, "warnings": warnings}
    except Exception as exc:
        errors.append(f"chunk: {exc}")
        return {"chunks": [], "errors": errors, "warnings": warnings}


def embed_node(state: PipelineState) -> dict:
    errors, warnings = _lists(state)
    chunks = state.get("chunks", [])
    if not chunks:
        return {"chunks": chunks, "errors": errors, "warnings": warnings}

    settings = get_settings()
    try:
        embedder = SentenceTransformerEmbedder(settings.embedding_model)
        vectors = embedder.embed([c.text for c in chunks])
        for chunk, vector in zip(chunks, vectors):
            chunk.embedding = vector
    except Exception as exc:
        warnings.append(f"embed: embeddings unavailable ({exc})")

    return {"chunks": chunks, "errors": errors, "warnings": warnings}


def store_vectors_node(state: PipelineState) -> dict:
    errors, warnings = _lists(state)
    settings = get_settings()
    chunks = state.get("chunks", [])
    document_id = state.get("db_document_id")

    if not settings.database_url or not document_id:
        if chunks:
            warnings.append("Skipping vector storage -- document was not persisted")
        return {"errors": errors, "warnings": warnings}

    if not any(c.embedding for c in chunks):
        return {"errors": errors, "warnings": warnings}

    try:
        with session_scope() as session:
            vector_writer.insert_chunk_embeddings(session, uuid.UUID(document_id), chunks)
    except Exception as exc:
        errors.append(f"store_vectors: {exc}")

    return {"errors": errors, "warnings": warnings}


def _route_after_extract_text(state: PipelineState) -> str:
    if state.get("fatal_error"):
        return "end"
    return "ocr_fallback" if state.get("needs_ocr") else "clean_text"


def _route_after_validate(state: PipelineState) -> str:
    return "end" if state.get("fatal_error") else "persist"


def build_graph():
    graph = StateGraph(PipelineState)

    graph.add_node("detect_source", detect_source_node)
    graph.add_node("load_document", load_document_node)
    graph.add_node("extract_text", extract_text_node)
    graph.add_node("ocr_fallback", ocr_fallback_node)
    graph.add_node("detect_handwriting", detect_handwriting_node)
    graph.add_node("clean_text", clean_text_node)
    graph.add_node("extract_entities", extract_entities_node)
    graph.add_node("extract_relations", extract_relations_node)
    graph.add_node("normalize", normalize_node)
    graph.add_node("resolve_entities", resolve_entities_node)
    graph.add_node("validate", validate_node)
    graph.add_node("persist", persist_node)
    graph.add_node("chunk", chunk_node)
    graph.add_node("embed", embed_node)
    graph.add_node("store_vectors", store_vectors_node)

    graph.set_entry_point("detect_source")
    graph.add_conditional_edges(
        "detect_source", lambda s: "end" if s.get("fatal_error") else "load_document",
        {"end": END, "load_document": "load_document"},
    )
    graph.add_conditional_edges(
        "load_document", lambda s: "end" if s.get("fatal_error") else "extract_text",
        {"end": END, "extract_text": "extract_text"},
    )
    graph.add_conditional_edges(
        "extract_text", _route_after_extract_text,
        {"end": END, "ocr_fallback": "ocr_fallback", "clean_text": "clean_text"},
    )
    graph.add_edge("ocr_fallback", "detect_handwriting")
    graph.add_edge("detect_handwriting", "clean_text")
    graph.add_edge("clean_text", "extract_entities")
    graph.add_edge("extract_entities", "extract_relations")
    graph.add_edge("extract_relations", "normalize")
    graph.add_edge("normalize", "resolve_entities")
    graph.add_edge("resolve_entities", "validate")
    graph.add_conditional_edges(
        "validate", _route_after_validate, {"end": END, "persist": "persist"},
    )
    graph.add_edge("persist", "chunk")
    graph.add_edge("chunk", "embed")
    graph.add_edge("embed", "store_vectors")
    graph.add_edge("store_vectors", END)

    return graph.compile()
