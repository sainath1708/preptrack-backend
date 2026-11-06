"""Pytest fixtures.

Each test gets its own in-memory SQLite database. ``StaticPool`` keeps a single
connection alive so every request sees the same database, mirroring production
behaviour closely enough to catch cross-user leakage.
"""

from __future__ import annotations

import os
from collections.abc import Callable, Generator
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

# Configure the environment *before* importing application modules.
os.environ.setdefault("ENVIRONMENT", "test")
os.environ.setdefault("SECRET_KEY", "test-secret-key-not-for-production")
os.environ.setdefault("DATABASE_URL", "sqlite://")

from database import Base, get_db  # noqa: E402
from main import app  # noqa: E402

TEST_DATABASE_URL = "sqlite://"


@pytest.fixture()
def engine() -> Generator[Engine, None, None]:
    """Fresh in-memory schema per test."""
    engine = create_engine(
        TEST_DATABASE_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    try:
        yield engine
    finally:
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


@pytest.fixture()
def session_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


@pytest.fixture()
def client(session_factory: sessionmaker[Session]) -> Generator[TestClient, None, None]:
    """TestClient whose requests use short-lived sessions on the test engine."""

    def override_get_db() -> Generator[Session, None, None]:
        db = session_factory()
        try:
            yield db
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture()
def user_factory(client: TestClient) -> Callable[..., dict[str, Any]]:
    """Register + log in a user and return their auth headers."""

    def create(
        email: str = "alice@example.com",
        password: str = "StrongPass123!",
    ) -> dict[str, Any]:
        register = client.post(
            "/auth/register",
            json={"email": email, "password": password},
        )
        assert register.status_code == 201, register.text

        login = client.post(
            "/auth/login",
            data={"username": email, "password": password},
        )
        assert login.status_code == 200, login.text

        token = login.json()["access_token"]
        return {
            "id": register.json()["id"],
            "email": register.json()["email"],
            "password": password,
            "token": token,
            "headers": {"Authorization": f"Bearer {token}"},
        }

    return create
