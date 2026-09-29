"""Environment-driven API configuration.

No API keys or credentials are hard-coded here.  Every setting reads
from the process environment (a local .env is loaded by python-dotenv
if present) and falls back to safe defaults.

Kept deliberately small — configuration surface stays narrow and
auditable.  Add a new setting only when it's actually needed by an
endpoint, not "just in case".
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from functools import lru_cache

from dotenv import load_dotenv

load_dotenv()


def _bool_env(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _int_env(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def _list_env(name: str, default: list[str]) -> list[str]:
    raw = os.getenv(name)
    if raw is None:
        return list(default)
    return [item.strip() for item in raw.split(",") if item.strip()]


@dataclass(frozen=True)
class APISettings:
    # Database ---------------------------------------------------------
    db_host: str
    db_port: int
    db_name: str
    db_user: str
    db_password: str | None
    db_pool_min: int
    db_pool_max: int

    # LLM (used by /query natural-language endpoint) -------------------
    groq_api_key: str | None
    llm_enabled: bool

    # HTTP / CORS ------------------------------------------------------
    cors_origins: list[str] = field(default_factory=list)
    request_timeout_seconds: float = 60.0

    # Observability ----------------------------------------------------
    log_level: str = "INFO"
    log_format: str = "json"  # "json" | "text"

    def db_config(self) -> dict:
        """Kwargs suitable for psycopg2.connect() / SimpleConnectionPool."""
        cfg: dict = {
            "host": self.db_host,
            "port": self.db_port,
            "dbname": self.db_name,
            "user": self.db_user,
        }
        if self.db_password:
            cfg["password"] = self.db_password
        return cfg


@lru_cache(maxsize=1)
def get_api_settings() -> APISettings:
    return APISettings(
        db_host=os.getenv("API_DB_HOST", os.getenv("DB_HOST", "localhost")),
        db_port=_int_env("API_DB_PORT", _int_env("DB_PORT", 5433)),
        db_name=os.getenv("API_DB_NAME", os.getenv("DB_NAME", "geo_intelligence")),
        db_user=os.getenv("API_DB_USER", os.getenv("DB_USER", "prasadhemadri99")),
        db_password=os.getenv("API_DB_PASSWORD") or os.getenv("DB_PASSWORD"),
        db_pool_min=_int_env("API_DB_POOL_MIN", 1),
        db_pool_max=_int_env("API_DB_POOL_MAX", 8),
        groq_api_key=os.getenv("GROQ_API_KEY"),
        llm_enabled=_bool_env("API_LLM_ENABLED", bool(os.getenv("GROQ_API_KEY"))),
        cors_origins=_list_env("API_CORS_ORIGINS", []),
        request_timeout_seconds=float(os.getenv("API_REQUEST_TIMEOUT_SECONDS", "60")),
        log_level=os.getenv("API_LOG_LEVEL", "INFO"),
        log_format=os.getenv("API_LOG_FORMAT", "json"),
    )


def reset_api_settings_cache() -> None:
    """Reset the cached settings — used only by tests that monkeypatch env vars."""
    get_api_settings.cache_clear()
