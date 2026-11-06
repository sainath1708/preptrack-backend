"""Problem CRUD, tenancy isolation, pagination, filtering and stats tests."""

from __future__ import annotations

from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient


def create_problem(client: TestClient, headers: dict[str, str], **overrides) -> dict:
    """POST a valid problem and return the created body."""
    payload: dict[str, object] = {
        "title": "Two Sum",
        "topic": "arrays",
        "difficulty": "easy",
    }
    payload.update(overrides)

    response = client.post("/problems", json=payload, headers=headers)
    assert response.status_code == 201, response.text
    return response.json()


# --------------------------------------------------------------------------- #
# Authentication is mandatory
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    ("method", "path", "kwargs"),
    [
        ("get", "/problems", {}),
        ("get", "/problems/1", {}),
        ("get", "/problems/revision-due", {}),
        ("get", "/stats", {}),
        ("post", "/problems", {"json": {"title": "T", "topic": "arrays", "difficulty": "easy"}}),
        ("put", "/problems/1", {"json": {"notes": "note"}}),
        ("put", "/problems/1/status", {"json": {"status": "solved"}}),
        ("delete", "/problems/1", {}),
    ],
)
def test_endpoints_require_authentication(
    client: TestClient, method: str, path: str, kwargs: dict
) -> None:
    response = getattr(client, method)(path, **kwargs)
    assert response.status_code == 401


# --------------------------------------------------------------------------- #
# Create
# --------------------------------------------------------------------------- #
def test_create_problem_defaults_to_pending(client: TestClient, user_factory) -> None:
    user = user_factory()

    body = create_problem(client, user["headers"])

    assert body["id"] > 0
    assert body["status"] == "pending"
    assert body["user_id"] == user["id"]
    assert body["title"] == "Two Sum"
    assert body["notes"] is None
    assert body["last_solved_date"] is None


def test_duplicate_title_and_topic_conflicts(client: TestClient, user_factory) -> None:
    user = user_factory()
    create_problem(client, user["headers"])

    response = client.post(
        "/problems",
        json={"title": "Two Sum", "topic": "arrays", "difficulty": "hard"},
        headers=user["headers"],
    )

    assert response.status_code == 409
    assert "already exists" in response.json()["detail"]


def test_same_title_allowed_for_different_topic(client: TestClient, user_factory) -> None:
    user = user_factory()
    create_problem(client, user["headers"], topic="arrays")

    response = client.post(
        "/problems",
        json={"title": "Two Sum", "topic": "hash-map", "difficulty": "easy"},
        headers=user["headers"],
    )

    assert response.status_code == 201


def test_same_title_allowed_for_different_users(
    client: TestClient, user_factory
) -> None:
    alice = user_factory("alice@example.com")
    bob = user_factory("bob@example.com")

    create_problem(client, alice["headers"])
    create_problem(client, bob["headers"])

    assert client.get("/problems", headers=bob["headers"]).json()["total"] == 1


# --------------------------------------------------------------------------- #
# Cross-tenant isolation
# --------------------------------------------------------------------------- #
def test_users_cannot_touch_other_users_problem(
    client: TestClient, user_factory
) -> None:
    alice = user_factory("alice@example.com")
    bob = user_factory("bob@example.com")
    problem = create_problem(client, alice["headers"])
    path = f"/problems/{problem['id']}"

    assert client.get(path, headers=bob["headers"]).status_code == 404
    assert (
        client.put(path, json={"title": "Hijacked"}, headers=bob["headers"]).status_code
        == 404
    )
    assert (
        client.put(
            f"{path}/status", json={"status": "solved"}, headers=bob["headers"]
        ).status_code
        == 404
    )
    assert (
        client.put(
            f"{path}/notes", json={"notes": "hijacked"}, headers=bob["headers"]
        ).status_code
        == 404
    )
    assert client.delete(path, headers=bob["headers"]).status_code == 404

    # Alice's data is untouched.
    still_there = client.get(path, headers=alice["headers"])
    assert still_there.status_code == 200
    assert still_there.json()["title"] == "Two Sum"
    assert still_there.json()["status"] == "pending"


def test_list_only_returns_own_problems(client: TestClient, user_factory) -> None:
    alice = user_factory("alice@example.com")
    bob = user_factory("bob@example.com")

    create_problem(client, alice["headers"], title="Alice 1")
    create_problem(client, alice["headers"], title="Alice 2")
    create_problem(client, bob["headers"], title="Bob 1")

    alice_list = client.get("/problems", headers=alice["headers"]).json()
    bob_list = client.get("/problems", headers=bob["headers"]).json()

    assert alice_list["total"] == 2
    assert {item["title"] for item in alice_list["items"]} == {"Alice 1", "Alice 2"}
    assert bob_list["total"] == 1
    assert bob_list["items"][0]["title"] == "Bob 1"


# --------------------------------------------------------------------------- #
# Read / pagination / filtering
# --------------------------------------------------------------------------- #
def test_pagination(client: TestClient, user_factory) -> None:
    user = user_factory()
    for index in range(1, 6):
        create_problem(client, user["headers"], title=f"Problem {index}")

    page = client.get(
        "/problems",
        params={"skip": 1, "limit": 2},
        headers=user["headers"],
    ).json()

    assert page["total"] == 5
    assert page["skip"] == 1
    assert page["limit"] == 2
    assert [item["title"] for item in page["items"]] == ["Problem 2", "Problem 3"]

    tail = client.get(
        "/problems", params={"skip": 4, "limit": 10}, headers=user["headers"]
    ).json()
    assert [item["title"] for item in tail["items"]] == ["Problem 5"]


def test_search_is_case_insensitive_and_escapes_wildcards(
    client: TestClient, user_factory
) -> None:
    user = user_factory()
    create_problem(client, user["headers"], title="Two Sum")
    create_problem(client, user["headers"], title="Three Sum")
    create_problem(client, user["headers"], title="Binary Search")
    create_problem(client, user["headers"], title="100% Array")

    lower = client.get("/problems", params={"search": "sum"}, headers=user["headers"])
    upper = client.get("/problems", params={"search": "SUM"}, headers=user["headers"])
    assert lower.json()["total"] == 2
    assert upper.json()["total"] == 2

    # A literal '%' must not behave like a LIKE wildcard.
    percent = client.get("/problems", params={"search": "%"}, headers=user["headers"])
    assert percent.json()["total"] == 1
    assert percent.json()["items"][0]["title"] == "100% Array"


def test_multi_criteria_filtering(client: TestClient, user_factory) -> None:
    user = user_factory()
    easy = create_problem(
        client, user["headers"], title="Two Sum", topic="Arrays", difficulty="easy"
    )
    create_problem(
        client, user["headers"], title="Merge K Lists", topic="heap", difficulty="hard"
    )
    medium = create_problem(
        client,
        user["headers"],
        title="Course Schedule",
        topic="graphs",
        difficulty="medium",
        status="revising",
    )
    client.put(
        f"/problems/{easy['id']}/status",
        json={"status": "solved"},
        headers=user["headers"],
    )

    by_difficulty = client.get(
        "/problems", params={"difficulty": "hard"}, headers=user["headers"]
    ).json()
    assert by_difficulty["total"] == 1

    # Topic matching is case-insensitive and exact.
    by_topic = client.get(
        "/problems", params={"topic": "arrays"}, headers=user["headers"]
    ).json()
    assert by_topic["total"] == 1
    assert by_topic["items"][0]["title"] == "Two Sum"

    by_status = client.get(
        "/problems", params={"status": "revising"}, headers=user["headers"]
    ).json()
    assert by_status["total"] == 1
    assert by_status["items"][0]["id"] == medium["id"]

    combined = client.get(
        "/problems",
        params={"status": "solved", "difficulty": "easy", "topic": "arrays", "search": "two"},
        headers=user["headers"],
    ).json()
    assert combined["total"] == 1


def test_get_single_problem(client: TestClient, user_factory) -> None:
    user = user_factory()
    problem = create_problem(client, user["headers"])

    response = client.get(f"/problems/{problem['id']}", headers=user["headers"])

    assert response.status_code == 200
    assert response.json()["id"] == problem["id"]


def test_missing_problem_returns_404(client: TestClient, user_factory) -> None:
    user = user_factory()
    response = client.get("/problems/424242", headers=user["headers"])
    assert response.status_code == 404


# --------------------------------------------------------------------------- #
# Revision reminders
# --------------------------------------------------------------------------- #
def test_revision_due_returns_only_due_owned_problems(
    client: TestClient, user_factory
) -> None:
    alice = user_factory("alice@example.com")
    bob = user_factory("bob@example.com")
    today = date.today()

    overdue = create_problem(
        client,
        alice["headers"],
        title="Overdue",
        revision_reminder=(today - timedelta(days=2)).isoformat(),
    )
    due_today = create_problem(
        client,
        alice["headers"],
        title="Due today",
        revision_reminder=today.isoformat(),
    )
    create_problem(
        client,
        alice["headers"],
        title="Future",
        revision_reminder=(today + timedelta(days=7)).isoformat(),
    )
    create_problem(client, alice["headers"], title="No reminder")
    create_problem(
        client,
        bob["headers"],
        title="Bob overdue",
        revision_reminder=(today - timedelta(days=1)).isoformat(),
    )

    response = client.get("/problems/revision-due", headers=alice["headers"])

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 2
    assert [item["id"] for item in body["items"]] == [overdue["id"], due_today["id"]]

    empty = client.get("/problems/revision-due", headers=bob["headers"])
    assert empty.json()["total"] == 1
    assert empty.json()["items"][0]["title"] == "Bob overdue"


def test_revision_due_pagination(client: TestClient, user_factory) -> None:
    user = user_factory()
    for index in range(3):
        create_problem(
            client,
            user["headers"],
            title=f"Due {index}",
            revision_reminder=(date.today() - timedelta(days=index + 1)).isoformat(),
        )

    page = client.get(
        "/problems/revision-due",
        params={"skip": 1, "limit": 1},
        headers=user["headers"],
    ).json()

    assert page["total"] == 3
    assert len(page["items"]) == 1


# --------------------------------------------------------------------------- #
# Update / delete
# --------------------------------------------------------------------------- #
def test_status_update_stamps_last_solved_date(
    client: TestClient, user_factory
) -> None:
    user = user_factory()
    problem = create_problem(client, user["headers"])

    response = client.put(
        f"/problems/{problem['id']}/status",
        json={"status": "solved"},
        headers=user["headers"],
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "solved"
    assert body["last_solved_date"] == date.today().isoformat()

    back_to_revising = client.put(
        f"/problems/{problem['id']}/status",
        json={"status": "revising"},
        headers=user["headers"],
    )
    assert back_to_revising.json()["status"] == "revising"


def test_notes_update_and_clear(client: TestClient, user_factory) -> None:
    user = user_factory()
    problem = create_problem(client, user["headers"])

    updated = client.put(
        f"/problems/{problem['id']}/notes",
        json={"notes": "Use a hash map."},
        headers=user["headers"],
    )
    assert updated.json()["notes"] == "Use a hash map."

    cleared = client.put(
        f"/problems/{problem['id']}/notes",
        json={"notes": None},
        headers=user["headers"],
    )
    assert cleared.status_code == 200
    assert cleared.json()["notes"] is None


def test_partial_update_leaves_other_fields_intact(
    client: TestClient, user_factory
) -> None:
    user = user_factory()
    problem = create_problem(client, user["headers"], notes="original")

    response = client.put(
        f"/problems/{problem['id']}",
        json={"difficulty": "hard"},
        headers=user["headers"],
    )

    body = response.json()
    assert body["difficulty"] == "hard"
    assert body["title"] == "Two Sum"
    assert body["notes"] == "original"


def test_delete_problem(client: TestClient, user_factory) -> None:
    user = user_factory()
    problem = create_problem(client, user["headers"])

    deleted = client.delete(f"/problems/{problem['id']}", headers=user["headers"])
    assert deleted.status_code == 204
    assert deleted.content == b""

    assert client.get(f"/problems/{problem['id']}", headers=user["headers"]).status_code == 404
    assert client.delete(f"/problems/{problem['id']}", headers=user["headers"]).status_code == 404


# --------------------------------------------------------------------------- #
# Statistics
# --------------------------------------------------------------------------- #
def test_stats_are_scoped_to_the_authenticated_user(
    client: TestClient, user_factory
) -> None:
    alice = user_factory("alice@example.com")
    bob = user_factory("bob@example.com")

    solved = create_problem(client, alice["headers"], title="Solved one")
    client.put(
        f"/problems/{solved['id']}/status",
        json={"status": "solved"},
        headers=alice["headers"],
    )
    create_problem(client, alice["headers"], title="Pending one")
    create_problem(client, alice["headers"], title="Revising one", status="revising")

    create_problem(client, bob["headers"], title="Bob solved", status="solved")
    create_problem(client, bob["headers"], title="Bob pending")

    alice_stats = client.get("/stats", headers=alice["headers"]).json()
    assert alice_stats == {
        "total_problems": 3,
        "solved_count": 1,
        "pending_count": 1,
        "revising_count": 1,
    }

    bob_stats = client.get("/stats", headers=bob["headers"]).json()
    assert bob_stats == {
        "total_problems": 2,
        "solved_count": 1,
        "pending_count": 1,
        "revising_count": 0,
    }


def test_stats_for_empty_account(client: TestClient, user_factory) -> None:
    user = user_factory()

    stats = client.get("/stats", headers=user["headers"]).json()

    assert stats == {
        "total_problems": 0,
        "solved_count": 0,
        "pending_count": 0,
        "revising_count": 0,
    }
