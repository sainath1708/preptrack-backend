"""Idempotent development seed data.

Usage:
    python seed.py

Creates one demo user plus five sample problems. Re-running is safe: the user is
looked up by email and each problem by its (title, topic) pair, and unique
constraint violations are swallowed rather than aborting the script.
"""

from __future__ import annotations

import os
from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from database import SessionLocal
from models import Difficulty, Problem, Status, User
from security import hash_password

DEMO_EMAIL = os.getenv("SEED_USER_EMAIL", "demo@preptrack.dev").strip().lower()
DEMO_PASSWORD = os.getenv("SEED_USER_PASSWORD", "DemoPass123!")

TODAY = date.today()

SAMPLE_PROBLEMS: list[dict[str, object]] = [
    {
        "title": "Two Sum",
        "topic": "arrays",
        "difficulty": Difficulty.easy,
        "status": Status.solved,
        "notes": "Hash map in one pass. O(n) time, O(n) space.",
        "last_solved_date": TODAY - timedelta(days=5),
        "revision_reminder": TODAY - timedelta(days=1),
    },
    {
        "title": "Longest Substring Without Repeating Characters",
        "topic": "sliding-window",
        "difficulty": Difficulty.medium,
        "status": Status.revising,
        "notes": "Sliding window with a last-index map; careful with left pointer jumps.",
        "last_solved_date": TODAY - timedelta(days=2),
        "revision_reminder": TODAY,
    },
    {
        "title": "Merge K Sorted Lists",
        "topic": "heap",
        "difficulty": Difficulty.hard,
        "status": Status.pending,
        "notes": "Min-heap of list heads; alternative is divide and conquer merge.",
        "last_solved_date": None,
        "revision_reminder": TODAY + timedelta(days=3),
    },
    {
        "title": "Course Schedule",
        "topic": "graphs",
        "difficulty": Difficulty.medium,
        "status": Status.solved,
        "notes": "Topological sort (Kahn's algorithm) detects cycles.",
        "last_solved_date": TODAY - timedelta(days=10),
        "revision_reminder": TODAY - timedelta(days=4),
    },
    {
        "title": "Climbing Stairs",
        "topic": "dynamic-programming",
        "difficulty": Difficulty.easy,
        "status": Status.revising,
        "notes": "Fibonacci recurrence with two rolling variables.",
        "last_solved_date": TODAY - timedelta(days=1),
        "revision_reminder": TODAY + timedelta(days=1),
    },
]


def get_or_create_demo_user(db) -> User:  # type: ignore[no-untyped-def]
    """Return the demo user, creating it when absent (race-safe)."""
    stmt = select(User).where(User.email == DEMO_EMAIL)

    user = db.execute(stmt).scalar_one_or_none()
    if user is not None:
        return user

    user = User(email=DEMO_EMAIL, hashed_password=hash_password(DEMO_PASSWORD))
    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        # Another process inserted the same email first.
        db.rollback()
        existing = db.execute(stmt).scalar_one_or_none()
        if existing is None:
            raise
        return existing

    db.refresh(user)
    return user


def seed() -> None:
    """Insert demo data, skipping anything that already exists."""
    db = SessionLocal()
    try:
        user = get_or_create_demo_user(db)

        created = 0
        skipped = 0
        for sample in SAMPLE_PROBLEMS:
            exists = db.execute(
                select(Problem.id).where(
                    Problem.user_id == user.id,
                    Problem.title == sample["title"],
                    Problem.topic == sample["topic"],
                )
            ).scalar_one_or_none()

            if exists is not None:
                skipped += 1
                continue

            db.add(Problem(user_id=user.id, **sample))  # type: ignore[arg-type]
            try:
                db.commit()
                created += 1
            except IntegrityError:
                db.rollback()
                skipped += 1

        print(
            f"Seed complete: user={DEMO_EMAIL} created={created} skipped={skipped}"
        )
        print(f"Login with {DEMO_EMAIL} / {DEMO_PASSWORD}")
    finally:
        db.close()


if __name__ == "__main__":
    seed()
