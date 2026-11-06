"""Database engine, declarative base and request-scoped session management.

The connection string is resolved in this order:

1. ``DATABASE_URL`` environment variable (loaded from ``.env`` when present).
2. ``sqlite:///./preptrack.db`` as a zero-configuration local fallback.

Render/Neon hand out ``postgres://...`` URLs, which SQLAlchemy 2.0 no longer
recognises. They are normalised to ``postgresql://`` before the engine is built.
"""

from __future__ import annotations

import os
from collections.abc import Generator

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

# Reads PrepTrack/.env into os.environ without ever overriding real env vars.
load_dotenv()

DEFAULT_DATABASE_URL = "sqlite:///./preptrack.db"


def build_database_url(raw_url: str | None = None) -> str:
    """Return a SQLAlchemy 2.0 compatible database URL.

    Args:
        raw_url: Explicit URL to normalise. Defaults to ``$DATABASE_URL``.
    """
    url = (raw_url if raw_url is not None else os.getenv("DATABASE_URL", "")).strip()
    if not url:
        return DEFAULT_DATABASE_URL

    # Heroku/Render/Neon historically emit the deprecated ``postgres://`` scheme.
    if url.startswith("postgres://"):
        url = f"postgresql://{url[len('postgres://') :]}"

    return url


DATABASE_URL = build_database_url()
IS_SQLITE = DATABASE_URL.startswith("sqlite")

engine = create_engine(
    DATABASE_URL,
    echo=os.getenv("SQL_ECHO", "0") == "1",
    # SQLite needs this for FastAPI's threadpool; Postgres ignores it.
    connect_args={"check_same_thread": False} if IS_SQLITE else {},
    # Neon suspends idle computes, so stale pooled connections are expected.
    pool_pre_ping=True,
    pool_recycle=1800,
)

SessionLocal = sessionmaker(
    bind=engine,
    autocommit=False,
    autoflush=False,
    expire_on_commit=False,
    class_=Session,
)


class Base(DeclarativeBase):
    """Declarative base shared by every ORM model.

    Alembic autogenerate reads ``Base.metadata``; the application itself never
    calls ``create_all`` (migrations own the schema).
    """


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency that yields a session and always closes it."""
    db = SessionLocal()
    try:
        yield db
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
