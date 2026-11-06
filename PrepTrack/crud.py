"""Data-access layer.

Every query is scoped by ``user_id`` so multi-tenancy is enforced in the
database layer, not just in the routers. All statements use SQLAlchemy 2.0
``select()`` / ``Session.execute()`` style.
"""

from __future__ import annotations

from datetime import date
from typing import Any

from sqlalchemy import case, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from models import Difficulty, Problem, Status, User
from schemas import ProblemCreate, ProblemUpdate, StatsResponse, UserCreate
from security import hash_password, verify_password


class ConflictError(Exception):
    """Raised when a write violates a unique constraint (mapped to HTTP 409)."""


def _escape_like(value: str) -> str:
    """Escape LIKE wildcards so user input is matched literally."""
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


# --------------------------------------------------------------------------- #
# Users
# --------------------------------------------------------------------------- #
def get_user(db: Session, user_id: int) -> User | None:
    """Fetch a user by primary key."""
    return db.get(User, user_id)


def get_user_by_email(db: Session, email: str) -> User | None:
    """Fetch a user by normalised email address."""
    stmt = select(User).where(User.email == email.strip().lower())
    return db.execute(stmt).scalar_one_or_none()


def create_user(db: Session, payload: UserCreate) -> User:
    """Persist a new user with a bcrypt-hashed password.

    Raises:
        ConflictError: if the email is already registered (race-safe).
    """
    user = User(email=payload.email, hashed_password=hash_password(payload.password))
    db.add(user)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise ConflictError("A user with this email already exists.") from exc

    db.refresh(user)
    return user


def authenticate_user(db: Session, email: str, password: str) -> User | None:
    """Return the user when the credentials match, otherwise ``None``."""
    user = get_user_by_email(db, email)
    if user is None:
        return None
    if not verify_password(password, user.hashed_password):
        return None
    return user


# --------------------------------------------------------------------------- #
# Problems
# --------------------------------------------------------------------------- #
def _problem_filters(
    user_id: int,
    *,
    search: str | None = None,
    topic: str | None = None,
    difficulty: Difficulty | None = None,
    status: Status | None = None,
) -> list[Any]:
    """Build the reusable WHERE clause shared by list/revision/stats queries."""
    filters: list[Any] = [Problem.user_id == user_id]

    if search:
        needle = _escape_like(search.strip())
        filters.append(Problem.title.ilike(f"%{needle}%", escape="\\"))

    if topic:
        filters.append(func.lower(Problem.topic) == topic.strip().lower())

    if difficulty is not None:
        filters.append(Problem.difficulty == difficulty)

    if status is not None:
        filters.append(Problem.status == status)

    return filters


def list_problems(
    db: Session,
    user_id: int,
    *,
    skip: int = 0,
    limit: int = 50,
    search: str | None = None,
    topic: str | None = None,
    difficulty: Difficulty | None = None,
    status: Status | None = None,
) -> tuple[list[Problem], int]:
    """Return one page of the user's problems plus the filtered total."""
    filters = _problem_filters(
        user_id,
        search=search,
        topic=topic,
        difficulty=difficulty,
        status=status,
    )

    count_stmt = select(func.count()).select_from(Problem).where(*filters)
    total = db.execute(count_stmt).scalar_one()

    stmt = (
        select(Problem)
        .where(*filters)
        .order_by(Problem.id.asc())
        .offset(skip)
        .limit(limit)
    )
    items = list(db.execute(stmt).scalars().all())
    return items, total


def get_problem(db: Session, user_id: int, problem_id: int) -> Problem | None:
    """Fetch one problem **only** if the given user owns it.

    Callers translate ``None`` into HTTP 404 so another tenant's problem ids
    remain indistinguishable from ids that do not exist.
    """
    stmt = select(Problem).where(Problem.id == problem_id, Problem.user_id == user_id)
    return db.execute(stmt).scalar_one_or_none()


def create_problem(db: Session, user_id: int, payload: ProblemCreate) -> Problem:
    """Insert a problem owned by ``user_id``.

    Raises:
        ConflictError: on a duplicate ``(title, topic, user_id)`` tuple.
    """
    problem = Problem(
        user_id=user_id,
        title=payload.title,
        topic=payload.topic,
        difficulty=payload.difficulty,
        status=payload.status,
        notes=payload.notes,
        last_solved_date=payload.last_solved_date,
        revision_reminder=payload.revision_reminder,
    )
    db.add(problem)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise ConflictError(
            "A problem with this title already exists for this topic."
        ) from exc

    db.refresh(problem)
    return problem


def update_problem(db: Session, problem: Problem, payload: ProblemUpdate) -> Problem:
    """Apply a partial update to ``problem``."""
    changes = payload.model_dump(exclude_unset=True)

    # Marking work as solved implies it was solved today unless stated otherwise.
    if changes.get("status") == Status.solved and "last_solved_date" not in changes:
        changes["last_solved_date"] = date.today()

    for field, value in changes.items():
        setattr(problem, field, value)

    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise ConflictError(
            "A problem with this title already exists for this topic."
        ) from exc

    db.refresh(problem)
    return problem


def update_status(db: Session, problem: Problem, new_status: Status) -> Problem:
    """Change only the status column, stamping ``last_solved_date`` when solved."""
    problem.status = new_status
    if new_status == Status.solved:
        problem.last_solved_date = date.today()
    db.commit()
    db.refresh(problem)
    return problem


def update_notes(db: Session, problem: Problem, notes: str | None) -> Problem:
    """Replace the free-text notes of a problem."""
    problem.notes = notes
    db.commit()
    db.refresh(problem)
    return problem


def delete_problem(db: Session, problem: Problem) -> None:
    """Hard-delete a problem the caller owns."""
    db.delete(problem)
    db.commit()


def list_revision_due(
    db: Session,
    user_id: int,
    *,
    today: date,
    skip: int = 0,
    limit: int = 50,
) -> tuple[list[Problem], int]:
    """Return problems whose revision reminder is due on/before ``today``."""
    filters = [
        Problem.user_id == user_id,
        Problem.revision_reminder.is_not(None),
        Problem.revision_reminder <= today,
    ]

    count_stmt = select(func.count()).select_from(Problem).where(*filters)
    total = db.execute(count_stmt).scalar_one()

    stmt = (
        select(Problem)
        .where(*filters)
        .order_by(Problem.revision_reminder.asc(), Problem.id.asc())
        .offset(skip)
        .limit(limit)
    )
    items = list(db.execute(stmt).scalars().all())
    return items, total


def get_stats(db: Session, user_id: int) -> StatsResponse:
    """Aggregate per-user status counters in a single round trip."""
    stmt = (
        select(
            func.count(Problem.id),
            func.count(case((Problem.status == Status.solved, Problem.id))),
            func.count(case((Problem.status == Status.pending, Problem.id))),
            func.count(case((Problem.status == Status.revising, Problem.id))),
        )
        .select_from(Problem)
        .where(Problem.user_id == user_id)
    )
    total, solved, pending, revising = db.execute(stmt).one()

    return StatsResponse(
        total_problems=total or 0,
        solved_count=solved or 0,
        pending_count=pending or 0,
        revising_count=revising or 0,
    )
