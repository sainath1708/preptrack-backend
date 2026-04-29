from datetime import date
from typing import List, Optional

from fastapi import Depends, FastAPI, HTTPException, Query, status
from sqlalchemy.orm import Session

from .database import Base, ProblemDB, SessionLocal, engine
from .models import (
    Difficulty,
    ProblemCreate,
    ProblemResponse,
    ProblemStatus,
    StatsResponse,
    UpdateNotesRequest,
    UpdateStatusRequest,
)

Base.metadata.create_all(bind=engine)

app = FastAPI(title="PrepTrack API")


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@app.get("/")
def root():
    return {"message": "PrepTrack API is running with SQLite"}


@app.post("/problems", response_model=ProblemResponse, status_code=status.HTTP_201_CREATED)
def create_problem(payload: ProblemCreate, db: Session = Depends(get_db)):
    item = ProblemDB(
        title=payload.title,
        difficulty=payload.difficulty.value,
        topic=payload.topic,
        status=ProblemStatus.pending.value,
        notes=payload.notes,
        last_solved_date=payload.last_solved_date,
        revision_reminder=payload.revision_reminder,
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@app.get("/problems", response_model=List[ProblemResponse])
def get_problems(
    difficulty: Optional[Difficulty] = Query(default=None),
    topic: Optional[str] = Query(default=None),
    db: Session = Depends(get_db),
):
    query = db.query(ProblemDB)
    if difficulty is not None:
        query = query.filter(ProblemDB.difficulty == difficulty.value)
    if topic is not None:
        query = query.filter(ProblemDB.topic.ilike(topic))
    return query.order_by(ProblemDB.id.asc()).all()


@app.put("/problems/{problem_id}/status", response_model=ProblemResponse)
def update_problem_status(
    problem_id: int,
    payload: UpdateStatusRequest,
    db: Session = Depends(get_db),
):
    item = db.query(ProblemDB).filter(ProblemDB.id == problem_id).first()
    if item is None:
        raise HTTPException(status_code=404, detail="Problem not found")

    item.status = payload.status.value
    if payload.status == ProblemStatus.solved:
        item.last_solved_date = date.today()

    db.commit()
    db.refresh(item)
    return item


@app.put("/problems/{problem_id}/notes", response_model=ProblemResponse)
def add_notes(problem_id: int, payload: UpdateNotesRequest, db: Session = Depends(get_db)):
    item = db.query(ProblemDB).filter(ProblemDB.id == problem_id).first()
    if item is None:
        raise HTTPException(status_code=404, detail="Problem not found")

    item.notes = payload.notes
    db.commit()
    db.refresh(item)
    return item


@app.delete("/problems/{problem_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_problem(problem_id: int, db: Session = Depends(get_db)):
    item = db.query(ProblemDB).filter(ProblemDB.id == problem_id).first()
    if item is None:
        raise HTTPException(status_code=404, detail="Problem not found")

    db.delete(item)
    db.commit()
    return


@app.get("/stats", response_model=StatsResponse)
def get_stats(db: Session = Depends(get_db)):
    all_items = db.query(ProblemDB).all()
    solved_count = sum(1 for p in all_items if p.status == ProblemStatus.solved.value)
    pending_count = sum(1 for p in all_items if p.status == ProblemStatus.pending.value)
    revision_count = sum(1 for p in all_items if p.status == ProblemStatus.revision.value)

    return StatsResponse(
        total_problems=len(all_items),
        solved_count=solved_count,
        pending_count=pending_count,
        revision_count=revision_count,
    )
