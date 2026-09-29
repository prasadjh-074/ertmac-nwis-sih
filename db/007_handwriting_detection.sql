-- 007: Add handwriting detection columns to document_pages.
-- These columns store detection results per page; they are nullable
-- to preserve backwards compatibility with existing rows.

ALTER TABLE document_pages
    ADD COLUMN IF NOT EXISTS handwriting_classification TEXT,
    ADD COLUMN IF NOT EXISTS handwriting_confidence     FLOAT,
    ADD COLUMN IF NOT EXISTS handwriting_ocr_status     TEXT,
    ADD COLUMN IF NOT EXISTS source_content_type        TEXT;

COMMENT ON COLUMN document_pages.handwriting_classification
    IS 'Content classification: typed, handwritten, mixed, unknown';
COMMENT ON COLUMN document_pages.handwriting_confidence
    IS 'Detection confidence [0, 1]';
COMMENT ON COLUMN document_pages.handwriting_ocr_status
    IS 'Handwriting OCR processing status';
COMMENT ON COLUMN document_pages.source_content_type
    IS 'Content type for downstream retrieval: typed, handwritten, mixed';
