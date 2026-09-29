"""Environment-driven configuration. No hardcoded credentials -- everything
comes from the environment (optionally loaded from a local .env via
python-dotenv). Importing this module never requires a live DB connection.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache

from dotenv import load_dotenv

load_dotenv()


def _bool_env(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    database_url: str | None
    test_database_url: str | None
    embedding_model: str
    ocr_enabled: bool
    ocr_language: str
    chunk_size: int
    chunk_overlap: int
    fuzzy_match_threshold: int
    log_level: str


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings(
        database_url=os.getenv("INGESTION_DATABASE_URL") or os.getenv("DATABASE_URL") or None,
        test_database_url=os.getenv("INGESTION_TEST_DATABASE_URL") or os.getenv("TEST_DATABASE_URL") or None,
        embedding_model=os.getenv("EMBEDDING_MODEL", "all-MiniLM-L6-v2"),
        ocr_enabled=_bool_env("OCR_ENABLED", True),
        ocr_language=os.getenv("OCR_LANGUAGE", "eng"),
        chunk_size=int(os.getenv("CHUNK_SIZE", "1200")),
        chunk_overlap=int(os.getenv("CHUNK_OVERLAP", "150")),
        fuzzy_match_threshold=int(os.getenv("FUZZY_MATCH_THRESHOLD", "92")),
        log_level=os.getenv("LOG_LEVEL", "INFO"),
    )
