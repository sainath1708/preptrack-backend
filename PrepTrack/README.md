# PrepTrack - Interview Preparation Tracker API

Backend API built with FastAPI.

## Files

- `main_inmemory.py` -> in-memory version (good for learning CRUD basics)
- `main.py` -> SQLite version (recommended final version)
- `models.py` -> request/response models (Pydantic)
- `database.py` -> SQLite and SQLAlchemy setup
- `requirements.txt` -> dependencies

## 1) Setup

Open terminal in `PrepTrack` folder.

Create virtual environment:

```bash
python -m venv .venv
```

Activate virtual environment (PowerShell):

```bash
.venv\Scripts\Activate.ps1
```

Install dependencies:

```bash
pip install -r requirements.txt
```

## 2) Run In-Memory Version

```bash
uvicorn main_inmemory:app --reload
```

Use this for beginner learning (data resets when server restarts).

## 3) Run SQLite Version

```bash
uvicorn main:app --reload
```

Use this for real project behavior (data stored in `preptrack.db`).

## 4) Open API Docs

After running server, open:

- Swagger UI: `http://127.0.0.1:8000/docs`
- ReDoc: `http://127.0.0.1:8000/redoc`

## 5) API Endpoints

- `POST /problems` -> create a problem
- `GET /problems` -> get all problems
- `GET /problems?difficulty=easy&topic=array` -> filter
- `PUT /problems/{id}/status` -> update status
- `PUT /problems/{id}/notes` -> update notes
- `DELETE /problems/{id}` -> delete problem
- `GET /stats` -> solved/pending/revision counts

## 6) Sample JSON

Create problem:

```json
{
  "title": "Two Sum",
  "difficulty": "easy",
  "topic": "array",
  "notes": "Try hashmap approach",
  "revision_reminder": "2026-05-05"
}
```

Update status:

```json
{
  "status": "solved"
}
```

Update notes:

```json
{
  "notes": "Solved in 15 minutes"
}
```

## 7) Common issue

If PowerShell blocks activation:

```bash
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
```

Then run:

```bash
.venv\Scripts\Activate.ps1
```
