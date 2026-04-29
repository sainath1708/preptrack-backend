from datetime import date
from typing import List, Optional

from fastapi import FastAPI, HTTPException, Query, status

try:
    from .models import (
        Difficulty,
        ProblemCreate,
        ProblemResponse,
        ProblemStatus,
        StatsResponse,
        UpdateNotesRequest,
        UpdateStatusRequest,
    )
except Exception:
    from models import (
        Difficulty,
        ProblemCreate,
        ProblemResponse,
        ProblemStatus,
        StatsResponse,
        UpdateNotesRequest,
        UpdateStatusRequest,
    )

app = FastAPI(title="PrepTrack API - In Memory")

problems: List[ProblemResponse] = []
next_id = 1


@app.get("/")
def root():
    return {"message": "PrepTrack API is running"}


@app.post("/problems", response_model=ProblemResponse, status_code=status.HTTP_201_CREATED)
def create_problem(payload: ProblemCreate):
    global next_id

    item = ProblemResponse(
        id=next_id,
        title=payload.title,
        difficulty=payload.difficulty,
        topic=payload.topic,
        status=ProblemStatus.pending,
        notes=payload.notes,
        last_solved_date=payload.last_solved_date,
        revision_reminder=payload.revision_reminder,
    )
    problems.append(item)
    next_id += 1
    return item


@app.get("/problems", response_model=List[ProblemResponse])
def get_problems(
    difficulty: Optional[Difficulty] = Query(default=None),
    topic: Optional[str] = Query(default=None),
):
    results = problems
    if difficulty is not None:
        results = [p for p in results if p.difficulty == difficulty]
    if topic is not None:
        results = [p for p in results if p.topic.lower() == topic.lower()]
    return results


@app.put("/problems/{problem_id}/status", response_model=ProblemResponse)
def update_problem_status(problem_id: int, payload: UpdateStatusRequest):
    for item in problems:
        if item.id == problem_id:
            item.status = payload.status
            if payload.status == ProblemStatus.solved:
                item.last_solved_date = date.today()
            return item
    raise HTTPException(status_code=404, detail="Problem not found")


@app.put("/problems/{problem_id}/notes", response_model=ProblemResponse)
def add_notes(problem_id: int, payload: UpdateNotesRequest):
    for item in problems:
        if item.id == problem_id:
            item.notes = payload.notes
            return item
    raise HTTPException(status_code=404, detail="Problem not found")


@app.delete("/problems/{problem_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_problem(problem_id: int):
    for index, item in enumerate(problems):
        if item.id == problem_id:
            problems.pop(index)
            return
    raise HTTPException(status_code=404, detail="Problem not found")


@app.get("/stats", response_model=StatsResponse)
def get_stats():
    solved_count = sum(1 for p in problems if p.status == ProblemStatus.solved)
    pending_count = sum(1 for p in problems if p.status == ProblemStatus.pending)
    revision_count = sum(1 for p in problems if p.status == ProblemStatus.revision)
    return StatsResponse(
        total_problems=len(problems),
        solved_count=solved_count,
        pending_count=pending_count,
        revision_count=revision_count,
    )
