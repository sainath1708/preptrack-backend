from datetime import date
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class Difficulty(str, Enum):
    easy = "easy"
    medium = "medium"
    hard = "hard"


class ProblemStatus(str, Enum):
    pending = "pending"
    solved = "solved"
    revision = "revision"


class ProblemBase(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    difficulty: Difficulty
    topic: str = Field(..., min_length=1, max_length=100)


class ProblemCreate(ProblemBase):
    notes: Optional[str] = None
    last_solved_date: Optional[date] = None
    revision_reminder: Optional[date] = None


class ProblemResponse(ProblemBase):
    id: int
    status: ProblemStatus
    notes: Optional[str] = None
    last_solved_date: Optional[date] = None
    revision_reminder: Optional[date] = None

    class Config:
        from_attributes = True


class UpdateStatusRequest(BaseModel):
    status: ProblemStatus


class UpdateNotesRequest(BaseModel):
    notes: str = Field(..., min_length=1)


class StatsResponse(BaseModel):
    total_problems: int
    solved_count: int
    pending_count: int
    revision_count: int
