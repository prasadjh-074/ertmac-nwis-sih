"""Tiny migration runner: applies ingestion migrations from db/ against
INGESTION_DATABASE_URL in lexical order, tracked in an
ingestion_schema_migrations bookkeeping table. No rollback support.

Usage:
    python -m ingestion.scripts.apply_migrations
"""
from __future__ import annotations

import logging
import sys
from pathlib import Path

import psycopg2

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from ingestion.config import get_settings

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger("apply_migrations")

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
MIGRATIONS_DIR = PROJECT_ROOT / "db"
INGESTION_MIGRATIONS = ["004_ingestion_reference_schema.sql", "005_ingestion_pipeline_schema.sql"]


def _dsn(database_url: str) -> str:
    # psycopg2 doesn't understand the "postgresql+psycopg2://" SQLAlchemy
    # dialect prefix -- strip it down to a plain "postgresql://" DSN.
    return database_url.replace("postgresql+psycopg2://", "postgresql://", 1)


def apply_migrations(database_url: str | None = None) -> list[str]:
    settings = get_settings()
    database_url = database_url or settings.database_url
    if not database_url:
        raise RuntimeError(
            "DATABASE_URL not configured -- see .env.example"
        )

    conn = psycopg2.connect(_dsn(database_url))
    conn.autocommit = False
    applied: list[str] = []
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS ingestion_schema_migrations (
                    filename TEXT PRIMARY KEY,
                    applied_at TIMESTAMPTZ NOT NULL DEFAULT now()
                )
                """
            )
        conn.commit()

        migration_files = [MIGRATIONS_DIR / name for name in INGESTION_MIGRATIONS
                           if (MIGRATIONS_DIR / name).exists()]
        for path in migration_files:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT 1 FROM ingestion_schema_migrations WHERE filename = %s",
                    (path.name,),
                )
                already_applied = cur.fetchone() is not None
            if already_applied:
                logger.info("Skipping already-applied migration: %s", path.name)
                continue

            logger.info("Applying migration: %s", path.name)
            sql = path.read_text()
            with conn.cursor() as cur:
                cur.execute(sql)
                cur.execute(
                    "INSERT INTO ingestion_schema_migrations (filename) VALUES (%s)",
                    (path.name,),
                )
            conn.commit()
            applied.append(path.name)
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

    return applied


if __name__ == "__main__":
    applied = apply_migrations()
    if applied:
        logger.info("Applied %d migration(s): %s", len(applied), ", ".join(applied))
    else:
        logger.info("No new migrations to apply.")
