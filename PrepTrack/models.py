"""SQLAlchemy 2.0 ORM models and domain enumerations."""

from __future__ import annotations

import enum
from datetime import date, datetime

from sqlalchemy import (
    Date,
    DateTime,
    Enum as SAEnum,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database import Base


class Difficulty(str, enum.Enum):
    """Problem difficulty. Stored as a VARCHAR with a CHECK constraint."""

    easy = "easy"
    medium = "medium"
    hard = "hard"


class Status(str, enum.Enum):
    """Revision lifecycle of a problem."""

    pending = "pending"
    solved = "solved"
    revising = "revising"


def _enum_type(enum_cls: type[enum.Enum], name: str) -> SAEnum:
    """Build a portable enum column type.

    ``native_enum=False`` keeps the schema identical on PostgreSQL and SQLite
    (VARCHAR + CHECK) so tests and local development behave like production.
    ``create_constraint=True`` turns the enum into a real CHECK constraint, so
    invalid values are rejected by the database itself.
    ``values_callable`` stores the lowercase *value* instead of the member name.
    """
    return SAEnum(
        enum_cls,
        name=name,
        native_enum=False,
        create_constraint=True,
        length=20,
        validate_strings=True,
        values_callable=lambda members: [member.value for member in members],
    )


DifficultyType = _enum_type(Difficulty, "ck_problems_difficulty")
StatusType = _enum_type(Status, "ck_problems_status")


class User(Base):
    """An authenticated tenant of the API."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    problems: Mapped[list[Problem]] = relationship(
        back_populates="owner",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    def __repr__(self) -> str:  # pragma: no cover - debugging helper
        return f"<User id={self.id} email={self.email!r}>"


class Problem(Base):
    """A practice problem owned by exactly one user."""

    __tablename__ = "problems"
    __table_args__ = (
        UniqueConstraint("title", "topic", "user_id", name="uq_problems_title_topic_user_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    topic: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    difficulty: Mapped[Difficulty] = mapped_column(DifficultyType, nullable=False, index=True)
    status: Mapped[Status] = mapped_column(
        StatusType,
        nullable=False,
        default=Status.pending,
        server_default=Status.pending.value,
        index=True,
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_solved_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    revision_reminder: Mapped[date | None] = mapped_column(Date, nullable=True, index=True)

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    owner: Mapped[User] = relationship(back_populates="problems")

    def __repr__(self) -> str:  # pragma: no cover - debugging helper
        return f"<Problem id={self.id} title={self.title!r} status={self.status.value!r}>"
