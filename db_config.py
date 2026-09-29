"""Single source of truth for the direct-psycopg2 connection parameters
used across nearby/, events/, risk/, retrieval/, document_retrieval/.

Historically these modules each hard-coded
``dict(host="localhost", port=5433, dbname="geo_intelligence", user="prasadhemadri99")``
inline. That is fine for local development against the Homebrew
PostgreSQL instance this project was built against, but breaks inside a
container, where the database is a separate service reachable at
``postgres:5432``, not ``localhost:5433``.

This module changes only *where the values come from* — every default
below is byte-for-byte identical to the literal that used to be
hard-coded, so local development is unaffected unless the corresponding
environment variables are set (as docker-compose.yml does for the
containerized deployment). No query, scoring, or retrieval logic lives
here or is touched by this change.
"""

from __future__ import annotations

import os


def get_db_config() -> dict:
    """Returns psycopg2.connect() kwargs, env-driven with the project's
    original local-development values as defaults."""
    cfg: dict = {
        "host": os.getenv("DB_HOST", "localhost"),
        "port": int(os.getenv("DB_PORT", "5433")),
        "dbname": os.getenv("DB_NAME", "geo_intelligence"),
        "user": os.getenv("DB_USER", "prasadhemadri99"),
    }
    password = os.getenv("DB_PASSWORD")
    if password:
        cfg["password"] = password
    return cfg
