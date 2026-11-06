"""Input validation and HTTP contract tests."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


@pytest.mark.parametrize(
    "payload",
    [
        {"topic": "arrays", "difficulty": "easy"},  # missing title
        {"title": "   ", "topic": "arrays", "difficulty": "easy"},  # blank title
        {"title": "Valid", "topic": "", "difficulty": "easy"},  # blank topic
        {"title": "Valid", "topic": "arrays", "difficulty": "extreme"},  # bad enum
        {"title": "a" * 201, "topic": "arrays", "difficulty": "easy"},  # too long
        {"title": "Valid", "topic": "t" * 101, "difficulty": "easy"},  # too long
        {"title": "Valid", "topic": "arrays", "difficulty": "easy", "notes": "n" * 5001},
        {"title": "Valid", "topic": "arrays", "difficulty": "easy", "revision_reminder": "31-12-2026"},
    ],
)
def test_create_problem_rejects_invalid_payloads(
    client: TestClient, user_factory, payload: dict
) -> None:
    user = user_factory()

    response = client.post("/problems", json=payload, headers=user["headers"])

    assert response.status_code == 422


def test_pagination_parameters_are_bounded(client: TestClient, user_factory) -> None:
    user = user_factory()

    for params in ({"limit": 0}, {"limit": 201}, {"skip": -1}):
        response = client.get("/problems", params=params, headers=user["headers"])
        assert response.status_code == 422, params


def test_invalid_status_filter_is_rejected(client: TestClient, user_factory) -> None:
    user = user_factory()

    response = client.get(
        "/problems", params={"status": "archived"}, headers=user["headers"]
    )

    assert response.status_code == 422


def test_invalid_status_update_is_rejected(client: TestClient, user_factory) -> None:
    user = user_factory()
    created = client.post(
        "/problems",
        json={"title": "Valid", "topic": "arrays", "difficulty": "easy"},
        headers=user["headers"],
    ).json()

    response = client.put(
        f"/problems/{created['id']}/status",
        json={"status": "done"},
        headers=user["headers"],
    )

    assert response.status_code == 422


def test_invalid_difficulty_filter_is_rejected(
    client: TestClient, user_factory
) -> None:
    user = user_factory()

    response = client.get(
        "/problems", params={"difficulty": "impossible"}, headers=user["headers"]
    )

    assert response.status_code == 422


def test_unknown_enums_are_documented_in_openapi(client: TestClient) -> None:
    """The enums must be exposed as string enums in the schema."""
    schema = client.get("/openapi.json").json()

    difficulty = schema["components"]["schemas"]["Difficulty"]
    status = schema["components"]["schemas"]["Status"]

    assert difficulty["enum"] == ["easy", "medium", "hard"]
    assert status["enum"] == ["pending", "solved", "revising"]
    assert difficulty["type"] == "string"


def test_health_endpoints(client: TestClient) -> None:
    assert client.get("/health").json() == {"status": "ok"}
    assert client.get("/").status_code == 200
