from __future__ import annotations

import os
from pathlib import Path

import pytest

from ingestion.config import get_settings

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"
SAMPLE_WELL_REPORT = FIXTURES_DIR / "sample_well_report.txt"


@pytest.fixture(scope="session")
def ingestion_test_db_url() -> str:
    url = get_settings().test_database_url
    if not url:
        pytest.skip("INGESTION_TEST_DATABASE_URL / TEST_DATABASE_URL not set")
    return url


@pytest.fixture(scope="session")
def ingestion_db_engine(ingestion_test_db_url):
    from ingestion.scripts.apply_migrations import apply_migrations
    from ingestion.storage.db import get_engine

    apply_migrations(database_url=ingestion_test_db_url)
    return get_engine(ingestion_test_db_url)


@pytest.fixture()
def ingestion_db_session(ingestion_db_engine):
    from sqlalchemy.orm import sessionmaker

    from ingestion.storage.models import (
        Document,
        DocumentChunk,
        DocumentPage,
        ExtractedEntity,
        ExtractedRelation,
        IngestionRun,
        ValidationResultRow,
    )

    session_factory = sessionmaker(bind=ingestion_db_engine, future=True, expire_on_commit=False)
    session = session_factory()
    for model in (ExtractedRelation, ExtractedEntity, ValidationResultRow,
                  DocumentChunk, DocumentPage, Document, IngestionRun):
        session.query(model).delete()
    session.commit()
    yield session
    session.rollback()
    session.close()


@pytest.fixture()
def ingestion_configured_database(ingestion_test_db_url, ingestion_db_engine, ingestion_db_session):
    original = os.environ.get("INGESTION_DATABASE_URL")
    os.environ["INGESTION_DATABASE_URL"] = ingestion_test_db_url
    get_settings.cache_clear()
    try:
        yield ingestion_test_db_url
    finally:
        if original is None:
            os.environ.pop("INGESTION_DATABASE_URL", None)
        else:
            os.environ["INGESTION_DATABASE_URL"] = original
        get_settings.cache_clear()
