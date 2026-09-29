"""SQLAlchemy engine/session factory. Importing this module never requires
a live DB -- an engine is only created (and DATABASE_URL validated) when
get_engine()/get_session() is actually called.
"""
from __future__ import annotations

from contextlib import contextmanager
from functools import lru_cache

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from ingestion.config import get_settings


@lru_cache(maxsize=None)
def get_engine(database_url: str | None = None) -> Engine:
    url = database_url or get_settings().database_url
    if not url:
        raise RuntimeError(
            "DATABASE_URL not configured -- see .env.example. "
            "Set it before performing any database operation."
        )
    return create_engine(url, future=True)


def get_session_factory(database_url: str | None = None) -> sessionmaker:
    engine = get_engine(database_url)
    return sessionmaker(bind=engine, future=True, expire_on_commit=False)


@contextmanager
def session_scope(database_url: str | None = None):
    factory = get_session_factory(database_url)
    session: Session = factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
