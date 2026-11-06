"""Initial schema: users and problems.

Revision ID: 0001_initial
Revises: None
Create Date: 2026-11-05

Notes:
    * Enums are created with ``native_enum=False`` + ``create_constraint=True``
      (VARCHAR + CHECK) so the same migration produces an identical schema on
      SQLite and PostgreSQL, and invalid values are rejected by the database.
    * ``CURRENT_TIMESTAMP`` is used as the server default: it is valid on both
      dialects, unlike ``now()`` or ``datetime('now')``.
"""

from __future__ import annotations

from typing import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0001_initial"
down_revision: str | None = None
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("hashed_password", sa.String(length=255), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    op.create_table(
        "problems",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("topic", sa.String(length=100), nullable=False),
        sa.Column(
            "difficulty",
            sa.Enum(
                "easy",
                "medium",
                "hard",
                name="ck_problems_difficulty",
                native_enum=False,
                create_constraint=True,
                length=20,
            ),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.Enum(
                "pending",
                "solved",
                "revising",
                name="ck_problems_status",
                native_enum=False,
                create_constraint=True,
                length=20,
            ),
            server_default="pending",
            nullable=False,
        ),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("last_solved_date", sa.Date(), nullable=True),
        sa.Column("revision_reminder", sa.Date(), nullable=True),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.UniqueConstraint(
            "title",
            "topic",
            "user_id",
            name="uq_problems_title_topic_user_id",
        ),
    )

    op.create_index("ix_problems_title", "problems", ["title"], unique=False)
    op.create_index("ix_problems_topic", "problems", ["topic"], unique=False)
    op.create_index("ix_problems_difficulty", "problems", ["difficulty"], unique=False)
    op.create_index("ix_problems_status", "problems", ["status"], unique=False)
    op.create_index(
        "ix_problems_revision_reminder",
        "problems",
        ["revision_reminder"],
        unique=False,
    )
    op.create_index("ix_problems_user_id", "problems", ["user_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_problems_user_id", table_name="problems")
    op.drop_index("ix_problems_revision_reminder", table_name="problems")
    op.drop_index("ix_problems_status", table_name="problems")
    op.drop_index("ix_problems_difficulty", table_name="problems")
    op.drop_index("ix_problems_topic", table_name="problems")
    op.drop_index("ix_problems_title", table_name="problems")
    op.drop_table("problems")

    op.drop_index("ix_users_email", table_name="users")
    op.drop_table("users")
