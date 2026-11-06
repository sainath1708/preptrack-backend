"""Problem CRUD, filtering, revision reminders and per-user statistics.

Every route depends on ``CurrentUser``; the user id is always taken from the
verified token and never from client input.
"""

from __future__ import annotations

from datetime import date
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, Response, status
from sqlalchemy.orm import Session

from crud import (
    create_problem as crud_create_problem,
    delete_problem as crud_delete_problem,
    get_problem as crud_get_problem,
    get_stats as crud_get_stats,
    list_problems as crud_list_problems,
    list_revision_due as crud_list_revision_due,
    update_notes as crud_update_notes,
    update_problem as crud_update_problem,
    update_status as crud_update_status,
)
from deps import CurrentUser, DbSession
from models import Difficulty, Problem, Status
from schemas import (
    PaginatedProblems,
    ProblemCreate,
    ProblemNotesUpdate,
    ProblemRead,
    ProblemStatusUpdate,
    ProblemUpdate,
    StatsResponse,
)

router = APIRouter(prefix="/problems", tags=["Problems"])
stats_router = APIRouter(tags=["Statistics"])

SkipParam = Annotated[int, Query(ge=0, description="Number of records to skip")]
LimitParam = Annotated[int, Query(ge=1, le=200, description="Page size (1-200)")]

NOT_FOUND = HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Problem not found")


def _get_owned_problem(db: Session, user_id: int, problem_id: int) -> Problem:
    """Load a problem the caller owns or raise 404 (never 403)."""
    problem = crud_get_problem(db, user_id, problem_id)
    if problem is None:
        raise NOT_FOUND
    return problem


@router.post(
    "",
    response_model=ProblemRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create a problem",
    responses={409: {"description": "Duplicate title for this topic"}},
)
def create_problem(
    payload: ProblemCreate,
    current_user: CurrentUser,
    db: DbSession,
) -> Problem:
    """Create a problem owned by the authenticated user."""
    return crud_create_problem(db, current_user.id, payload)


@router.get(
    "",
    response_model=PaginatedProblems,
    summary="List, search and filter your problems",
)
def list_problems(
    current_user: CurrentUser,
    db: DbSession,
    skip: SkipParam = 0,
    limit: LimitParam = 50,
    search: Annotated[
        str | None, Query(max_length=200, description="Case-insensitive title search")
    ] = None,
    topic: Annotated[str | None, Query(max_length=100)] = None,
    difficulty: Annotated[Difficulty | None, Query()] = None,
    problem_status: Annotated[
        Status | None, Query(alias="status", description="Filter by revision status")
    ] = None,
) -> PaginatedProblems:
    """Paginated listing scoped to the caller, newest ids last."""
    items, total = crud_list_problems(
        db,
        current_user.id,
        skip=skip,
        limit=limit,
        search=search,
        topic=topic,
        difficulty=difficulty,
        status=problem_status,
    )
    return PaginatedProblems(items=items, total=total, skip=skip, limit=limit)


# Declared before /{problem_id} so the literal path wins the route match.
@router.get(
    "/revision-due",
    response_model=PaginatedProblems,
    summary="Problems due for revision today or earlier",
)
def list_revision_due(
    current_user: CurrentUser,
    db: DbSession,
    skip: SkipParam = 0,
    limit: LimitParam = 50,
) -> PaginatedProblems:
    """Return the caller's problems whose ``revision_reminder`` has come due."""
    items, total = crud_list_revision_due(
        db,
        current_user.id,
        today=date.today(),
        skip=skip,
        limit=limit,
    )
    return PaginatedProblems(items=items, total=total, skip=skip, limit=limit)


@router.get(
    "/{problem_id}",
    response_model=ProblemRead,
    summary="Get one of your problems",
    responses={404: {"description": "Not found or not owned by you"}},
)
def get_problem(problem_id: int, current_user: CurrentUser, db: DbSession) -> Problem:
    return _get_owned_problem(db, current_user.id, problem_id)


@router.put(
    "/{problem_id}",
    response_model=ProblemRead,
    summary="Update a problem (partial payload allowed)",
    responses={404: {"description": "Not found or not owned by you"}},
)
def update_problem(
    problem_id: int,
    payload: ProblemUpdate,
    current_user: CurrentUser,
    db: DbSession,
) -> Problem:
    """Send only the fields you want to change; omitted fields are untouched."""
    problem = _get_owned_problem(db, current_user.id, problem_id)
    return crud_update_problem(db, problem, payload)


@router.put(
    "/{problem_id}/status",
    response_model=ProblemRead,
    summary="Update only the status",
    responses={404: {"description": "Not found or not owned by you"}},
)
def update_problem_status(
    problem_id: int,
    payload: ProblemStatusUpdate,
    current_user: CurrentUser,
    db: DbSession,
) -> Problem:
    problem = _get_owned_problem(db, current_user.id, problem_id)
    return crud_update_status(db, problem, payload.status)


@router.put(
    "/{problem_id}/notes",
    response_model=ProblemRead,
    summary="Update only the notes",
    responses={404: {"description": "Not found or not owned by you"}},
)
def update_problem_notes(
    problem_id: int,
    payload: ProblemNotesUpdate,
    current_user: CurrentUser,
    db: DbSession,
) -> Problem:
    problem = _get_owned_problem(db, current_user.id, problem_id)
    return crud_update_notes(db, problem, payload.notes)


@router.delete(
    "/{problem_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    summary="Delete a problem",
    responses={404: {"description": "Not found or not owned by you"}},
)
def delete_problem(problem_id: int, current_user: CurrentUser, db: DbSession) -> Response:
    problem = _get_owned_problem(db, current_user.id, problem_id)
    crud_delete_problem(db, problem)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@stats_router.get(
    "/stats",
    response_model=StatsResponse,
    summary="Aggregated counters for the authenticated user",
)
def get_stats(current_user: CurrentUser, db: DbSession) -> StatsResponse:
    """Counts are always scoped to the caller's own problems."""
    return crud_get_stats(db, current_user.id)
