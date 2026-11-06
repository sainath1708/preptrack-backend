"""Registration, login and JWT lifecycle tests."""

from __future__ import annotations

from datetime import timedelta

from fastapi.testclient import TestClient

from security import ACCESS_TOKEN_EXPIRE_MINUTES, create_access_token


def test_register_creates_user_and_normalises_email(client: TestClient) -> None:
    response = client.post(
        "/auth/register",
        json={"email": "  Alice@Example.COM  ", "password": "StrongPass123!"},
    )

    assert response.status_code == 201
    body = response.json()
    assert body["email"] == "alice@example.com"
    assert isinstance(body["id"], int)
    assert "created_at" in body
    # The hash must never leave the database.
    assert "hashed_password" not in body
    assert "password" not in body


def test_register_duplicate_email_returns_409(client: TestClient) -> None:
    payload = {"email": "alice@example.com", "password": "StrongPass123!"}
    assert client.post("/auth/register", json=payload).status_code == 201

    duplicate = client.post("/auth/register", json=payload)
    assert duplicate.status_code == 409
    assert "already exists" in duplicate.json()["detail"]

    # Emails are normalised, so case differences are duplicates too.
    upper = client.post(
        "/auth/register",
        json={"email": "ALICE@example.com", "password": "StrongPass123!"},
    )
    assert upper.status_code == 409


def test_register_rejects_invalid_payloads(client: TestClient) -> None:
    invalid_bodies = [
        {"email": "not-an-email", "password": "StrongPass123!"},
        {"email": "bob@example.com", "password": "short"},
        {"email": "bob@example.com", "password": "a" * 73},
        # 40 chars but 80 UTF-8 bytes: bcrypt limit is byte-based.
        {"email": "bob@example.com", "password": "é" * 40},
        {"email": "bob@example.com"},
    ]

    for body in invalid_bodies:
        response = client.post("/auth/register", json=body)
        assert response.status_code == 422, body


def test_login_returns_oauth2_bearer_token(
    client: TestClient, user_factory
) -> None:
    user = user_factory()

    response = client.post(
        "/auth/login",
        data={"username": user["email"], "password": user["password"]},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["access_token"]
    assert body["expires_in"] == ACCESS_TOKEN_EXPIRE_MINUTES * 60


def test_login_with_wrong_password_is_rejected(client: TestClient, user_factory) -> None:
    user = user_factory()

    response = client.post(
        "/auth/login",
        data={"username": user["email"], "password": "WrongPassword123!"},
    )

    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"


def test_login_with_unknown_email_is_rejected(client: TestClient) -> None:
    response = client.post(
        "/auth/login",
        data={"username": "ghost@example.com", "password": "StrongPass123!"},
    )
    assert response.status_code == 401


def test_me_requires_authentication(client: TestClient) -> None:
    assert client.get("/auth/me").status_code == 401


def test_me_returns_authenticated_user(client: TestClient, user_factory) -> None:
    user = user_factory()

    response = client.get("/auth/me", headers=user["headers"])

    assert response.status_code == 200
    assert response.json()["email"] == user["email"]


def test_tampered_token_is_rejected(client: TestClient, user_factory) -> None:
    user = user_factory()
    tampered = f"{user['token'][:-4]}beef"

    response = client.get("/auth/me", headers={"Authorization": f"Bearer {tampered}"})
    assert response.status_code == 401


def test_expired_token_is_rejected(client: TestClient, user_factory) -> None:
    user = user_factory()
    expired = create_access_token(user["id"], expires_delta=timedelta(seconds=-5))

    response = client.get("/auth/me", headers={"Authorization": f"Bearer {expired}"})
    assert response.status_code == 401


def test_token_for_deleted_user_is_rejected(client: TestClient) -> None:
    orphan_token = create_access_token(999_999)

    response = client.get("/auth/me", headers={"Authorization": f"Bearer {orphan_token}"})
    assert response.status_code == 401
