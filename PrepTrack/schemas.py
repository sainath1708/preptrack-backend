"""Pydantic V2 request/response contracts."""

from __future__ import annotations

from datetime import date, datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from models import Difficulty, Status

# bcrypt only hashes the first 72 bytes; longer secrets are silently truncated
# by some backends and must be rejected instead.
MAX_BCRYPT_BYTES = 72

Title = Annotated[str, Field(min_length=1, max_length=200)]
Topic = Annotated[str, Field(min_length=1, max_length=100)]


class UserCreate(BaseModel):
    """Registration payload."""

    email: EmailStr
    password: str = Field(min_length=8, max_length=MAX_BCRYPT_BYTES)

    @field_validator("email")
    @classmethod
    def normalise_email(cls, value: str) -> str:
        return value.strip().lower()

    @field_validator("password")
    @classmethod
    def password_fits_bcrypt(cls, value: str) -> str:
        if len(value.encode("utf-8")) > MAX_BCRYPT_BYTES:
            raise ValueError(f"password must be at most {MAX_BCRYPT_BYTES} bytes")
        return value


class UserRead(BaseModel):
    """Public representation of a user. Never exposes the password hash."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    email: EmailStr
    created_at: datetime


class Token(BaseModel):
    """OAuth2 bearer token returned by ``POST /auth/login``."""

    access_token: str
    token_type: str = "bearer"
    expires_in: int


class ProblemBase(BaseModel):
    title: Title
    topic: Topic
    difficulty: Difficulty
    notes: str | None = Field(default=None, max_length=5000)
    last_solved_date: date | None = None
    revision_reminder: date | None = None

    @field_validator("title", "topic")
    @classmethod
    def reject_blank(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("must not be blank")
        return stripped


class ProblemCreate(ProblemBase):
    """Payload for creating a problem. New problems default to ``pending``."""

    status: Status = Status.pending


class ProblemUpdate(BaseModel):
    """Partial update; only fields present in the request body are applied."""

    title: Title | None = None
    topic: Topic | None = None
    difficulty: Difficulty | None = None
    status: Status | None = None
    notes: str | None = Field(default=None, max_length=5000)
    last_solved_date: date | None = None
    revision_reminder: date | None = None

    @field_validator("title", "topic")
    @classmethod
    def reject_blank(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        if not stripped:
            raise ValueError("must not be blank")
        return stripped


class ProblemStatusUpdate(BaseModel):
    status: Status


class ProblemNotesUpdate(BaseModel):
    notes: str | None = Field(default=None, max_length=5000)


class ProblemRead(ProblemBase):
    """Full problem representation returned to its owner."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    status: Status
    user_id: int
    created_at: datetime
    updated_at: datetime


class PaginatedProblems(BaseModel):
    items: list[ProblemRead]
    total: int
    skip: int
    limit: int


class StatsResponse(BaseModel):
    """Aggregated counters scoped to the authenticated user."""

    total_problems: int
    solved_count: int
    pending_count: int
    revising_count: int
