# PrepTrack API

A production-ready, **multi-tenant REST API** for tracking interview-preparation
problems. Built with FastAPI, SQLAlchemy 2.0 and PostgreSQL, secured with OAuth2
JWT bearer tokens, and shipped with Alembic migrations, Docker tooling, seed
data and a pytest suite.

Every record is owned by exactly one user. The API never trusts a client-supplied
`user_id`: ownership is derived from the verified JWT and enforced in the data
layer, so one tenant's problem ids are indistinguishable from ids that do not
exist (both return `404`).

---

## Table of contents

1. [Tech stack](#tech-stack)
2. [Features](#features)
3. [Project structure](#project-structure)
4. [Local setup — Docker](#local-setup--docker)
5. [Local setup — Python venv](#local-setup--python-venv)
6. [Configuration](#configuration)
7. [Database migrations (Alembic)](#database-migrations-alembic)
8. [Seeding demo data](#seeding-demo-data)
9. [API reference](#api-reference)
10. [Testing](#testing)
11. [Deployment: Neon + Render](#deployment-neon--render)
12. [Operations & security checklist](#operations--security-checklist)
13. [Troubleshooting](#troubleshooting)

---

## Tech stack

| Layer | Choice | Why |
| --- | --- | --- |
| Runtime | Python 3.10+ | Modern typing (`str \| None`), broad host support |
| Web framework | FastAPI | Async ASGI, OpenAPI generation, dependency injection |
| ORM | SQLAlchemy 2.0 | `select()` / `Session.execute()` typed query API |
| Validation | Pydantic V2 | Strict request/response contracts, email + enum validation |
| Database | PostgreSQL (Neon) / SQLite | Same SQLAlchemy models for both |
| Driver | `psycopg2-binary` | No compiler needed on Render or in Docker |
| Migrations | Alembic | Versioned, reversible schema changes; no `create_all` |
| Auth | `passlib[bcrypt]` + `PyJWT` | bcrypt password hashing, HS256 JWTs |
| Tests | `pytest` + `TestClient` | 52 tests on an isolated in-memory database |
| Packaging | Docker + Compose | Reproducible local stack with a Postgres service |

---

## Features

**Multi-tenancy & auth**
- `users` table with bcrypt-hashed passwords (never returned by the API).
- `POST /auth/register`, `POST /auth/login` (OAuth2 password flow → JWT), `GET /auth/me`.
- Stateless HS256 tokens with `sub`, `iat`, `exp` and a `type` claim; expired,
  tampered and orphaned tokens are all rejected with `401`.
- Every problem read/write is filtered by the authenticated `user_id`;
  cross-tenant access returns `404`, never `403` (no resource enumeration).
- `ON DELETE CASCADE` on `problems.user_id`, plus ORM-level cascade.

**Problem tracking**
- Full CRUD on `/problems`, plus narrow `status` and `notes` update endpoints.
- String enums enforced in Python **and** by database `CHECK` constraints
  (`Difficulty`: `easy|medium|hard`, `Status`: `pending|solved|revising`).
- Marking a problem `solved` automatically stamps `last_solved_date`.
- `UniqueConstraint(title, topic, user_id)` → duplicate inserts return `409`.

**Querying**
- Pagination via `skip` / `limit` (1–200) with a `total` count.
- Case-insensitive title search with LIKE-wildcard escaping (`%` and `_` are literal).
- Multi-criteria filtering by `topic`, `difficulty` and `status` (combinable).
- `GET /problems/revision-due` returns reminders due today or earlier.
- `GET /stats` aggregates total / solved / pending / revising in one query, scoped to the caller.

**Operational**
- Alembic owns the schema (`alembic upgrade head`); migrations run on container start.
- `/health` liveness endpoint wired to Render's health check.
- Idempotent `seed.py` that tolerates duplicate runs.
- Non-root Docker image, strict `.gitignore`, `.env.example` for every variable.

---

## Project structure

```
PrepTrack/
├── alembic/
│   ├── env.py                     # reads DATABASE_URL, binds Base.metadata
│   ├── script.py.mako             # revision template
│   └── versions/
│       └── 0001_initial_schema.py # users + problems + indexes + CHECK constraints
├── routers/
│   ├── __init__.py
│   ├── auth.py                    # /auth/register, /auth/login, /auth/me
│   └── problems.py                # /problems CRUD, /problems/revision-due, /stats
├── tests/
│   ├── conftest.py                # in-memory SQLite fixtures, auth helper
│   ├── test_auth.py               # registration, login, token lifecycle
│   ├── test_problems.py           # CRUD, tenancy isolation, filters, stats
│   └── test_validation.py         # 422 contracts, enum/OpenAPI assertions
├── .dockerignore
├── .env.example
├── .gitignore
├── alembic.ini
├── crud.py                        # data-access layer (all queries user-scoped)
├── database.py                    # engine, SessionLocal, Base, get_db
├── deps.py                        # DbSession + CurrentUser dependencies
├── docker-compose.yml             # api + postgres for local development
├── Dockerfile                     # slim, non-root, migrate-then-serve
├── main.py                        # app wiring, 409 handler, health endpoints
├── models.py                      # User, Problem, Difficulty, Status
├── pytest.ini
├── requirements.txt               # runtime dependencies (pinned)
├── requirements-dev.txt           # + pytest, httpx
├── schemas.py                     # Pydantic V2 request/response models
├── security.py                    # bcrypt hashing, JWT encode/decode
└── seed.py                        # demo user + 5 sample problems
```

---

## Local setup — Docker

Requires Docker Desktop / Docker Engine with Compose v2.

```bash
cd PrepTrack
docker compose up --build
```

`docker-compose.yml` starts PostgreSQL 16 (with a `pg_isready` healthcheck) and
the API. The API container runs `alembic upgrade head` before starting uvicorn,
so the schema is ready on first boot.

Then, in a second terminal:

```bash
docker compose exec api python seed.py     # optional demo data
```

| URL | Purpose |
| --- | --- |
| http://localhost:8000/docs | Swagger UI (use **Authorize** after logging in) |
| http://localhost:8000/redoc | ReDoc |
| http://localhost:8000/health | Liveness probe |

Stop the stack with `docker compose down` (add `-v` to also drop the database volume).
Source is bind-mounted, so `--reload` picks up code changes; dependency changes
need `docker compose up --build` again.

---

## Local setup — Python venv

Requires Python 3.10+ and a reachable PostgreSQL, **or** no database at all —
the app falls back to `sqlite:///./preptrack.db` when `DATABASE_URL` is unset.

```bash
cd PrepTrack
python -m venv .venv

# Windows (PowerShell)
.venv\Scripts\Activate.ps1
# macOS / Linux
source .venv/bin/activate

pip install -r requirements-dev.txt
cp .env.example .env        # then set SECRET_KEY (and DATABASE_URL if using Postgres)
```

If PowerShell blocks activation:
`Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass`

Create the schema and (optionally) demo data:

```bash
alembic upgrade head
python seed.py
uvicorn main:app --reload
```

Run the tests:

```bash
pytest
```

---

## Configuration

Configuration is read from the environment (and `.env`, via `python-dotenv`).
See `.env.example` for a copy-paste template.

| Variable | Default | Required | Description |
| --- | --- | --- | --- |
| `DATABASE_URL` | `sqlite:///./preptrack.db` | Production | SQLAlchemy URL. `postgres://` is auto-rewritten to `postgresql://`. |
| `SECRET_KEY` | dev-only placeholder | **Production** | JWT signing key. The app refuses to start in `ENVIRONMENT=production` without it. |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `60` | No | Access-token lifetime. |
| `ENVIRONMENT` | `development` | No | `production` enables strict config checks. |
| `SQL_ECHO` | `0` | No | `1` logs every SQL statement. |
| `SEED_USER_EMAIL` | `demo@preptrack.dev` | No | Seed user email. |
| `SEED_USER_PASSWORD` | `DemoPass123!` | No | Seed user password. |

Generate a strong secret:

```bash
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

---

## Database migrations (Alembic)

`alembic.ini` contains **no** database URL. `alembic/env.py` imports
`DATABASE_URL` from `database.py`, so the app and the migration tool always
target the same database.

Common commands (run from `PrepTrack/`):

```bash
alembic upgrade head              # apply all migrations
alembic current                   # show the revision the DB is on
alembic history --verbose         # full revision history
alembic downgrade -1              # roll back one revision
alembic downgrade base            # drop everything managed by Alembic
alembic check                     # fail if models drift from migrations
```

Create a new migration after changing models:

```bash
alembic revision --autogenerate -m "add contest field"
# ALWAYS review the generated file before applying it
alembic upgrade head
```

Notes:
- `alembic/env.py` enables `render_as_batch` for SQLite (which cannot `ALTER`
  most columns) and disables it implicitly for PostgreSQL.
- Enum columns are `VARCHAR` + `CHECK` (`native_enum=False`), so the schema is
  identical across SQLite and PostgreSQL and needs no `CREATE TYPE` handling.
- Never call `Base.metadata.create_all()` — migrations are the single source of truth.

---

## Seeding demo data

```bash
python seed.py
```

Creates `demo@preptrack.dev` / `DemoPass123!` (override with `SEED_USER_EMAIL`
and `SEED_USER_PASSWORD`) and five problems across `arrays`, `sliding-window`,
`heap`, `graphs` and `dynamic-programming`. Re-running is safe: existing rows are
skipped and unique-constraint violations are caught.

```bash
curl -X POST http://localhost:8000/auth/login \
  -d "username=demo@preptrack.dev&password=DemoPass123!"
```

---

## API reference

Base URL: `http://localhost:8000` (or your Render URL).
All `/problems` and `/stats` routes require `Authorization: Bearer <token>`.

| Method | Path | Auth | Description |
| --- | --- | --- | --- |
| `GET` | `/` | Public | Service banner and version. |
| `GET` | `/health` | Public | Liveness probe for Render. |
| `POST` | `/auth/register` | Public | Create an account. `201`, `409` if the email exists. |
| `POST` | `/auth/login` | Public | OAuth2 password flow (`username` = email, `password`). Returns a JWT. |
| `GET` | `/auth/me` | Bearer | Return the authenticated user. |
| `POST` | `/problems` | Bearer | Create a problem. `409` on duplicate `(title, topic)`. |
| `GET` | `/problems` | Bearer | Paginated list. Query: `skip`, `limit`, `search`, `topic`, `difficulty`, `status`. |
| `GET` | `/problems/revision-due` | Bearer | Problems with `revision_reminder <= today`. Query: `skip`, `limit`. |
| `GET` | `/problems/{problem_id}` | Bearer | Fetch one owned problem. `404` if not yours. |
| `PUT` | `/problems/{problem_id}` | Bearer | Partial update — send only changed fields. |
| `PUT` | `/problems/{problem_id}/status` | Bearer | Update `status` only (stamps `last_solved_date` when solved). |
| `PUT` | `/problems/{problem_id}/notes` | Bearer | Update `notes` only (`{"notes": null}` clears them). |
| `DELETE` | `/problems/{problem_id}` | Bearer | Delete an owned problem. `204`, `404` if not yours. |
| `GET` | `/stats` | Bearer | `{total_problems, solved_count, pending_count, revising_count}` for the caller. |

**Status codes:** `401` missing/invalid token · `404` unknown *or* foreign resource ·
`409` duplicate · `422` validation error.

### Example flow

```bash
# 1. Register
curl -X POST http://localhost:8000/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email":"you@example.com","password":"StrongPass123!"}'

# 2. Log in and capture the token
TOKEN=$(curl -s -X POST http://localhost:8000/auth/login \
  -d "username=you@example.com&password=StrongPass123!" \
  | python -c "import sys,json;print(json.load(sys.stdin)['access_token'])")

# 3. Create a problem
curl -X POST http://localhost:8000/problems \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"title":"Two Sum","topic":"arrays","difficulty":"easy",
       "notes":"Hash map, one pass","revision_reminder":"2026-05-05"}'

# 4. Search + filter + paginate
curl -G http://localhost:8000/problems \
  -H "Authorization: Bearer $TOKEN" \
  --data-urlencode "search=sum" \
  --data-urlencode "difficulty=easy" \
  --data-urlencode "status=revising" \
  --data-urlencode "skip=0" --data-urlencode "limit=20"

# 5. Mark solved, review what is due, read stats
curl -X PUT http://localhost:8000/problems/1/status \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"status":"solved"}'

curl http://localhost:8000/problems/revision-due -H "Authorization: Bearer $TOKEN"
curl http://localhost:8000/stats -H "Authorization: Bearer $TOKEN"
```

Paginated responses are shaped as
`{"items": [...], "total": 12, "skip": 0, "limit": 20}`.

---

## Testing

```bash
pytest                      # 52 tests, in-memory SQLite, no external services
pytest -v tests/test_problems.py::test_users_cannot_touch_other_users_problem
```

| Area | Coverage |
| --- | --- |
| Registration | Success, email normalisation, duplicate `409`, invalid email, short/over-long passwords, bcrypt byte limit |
| Login & tokens | Bearer token shape, wrong password, unknown user, `/auth/me`, tampered token, expired token, deleted-user token |
| Tenancy isolation | Second user gets `404` for GET/PUT/status/notes/DELETE; lists and stats never leak |
| CRUD | Defaults, duplicate title `409`, same title across topics/users, partial updates, notes clearing, delete `204` then `404` |
| Querying | Pagination + totals, case-insensitive search, literal `%`, topic/difficulty/status filters, combined filters, revision-due window |
| Stats | Per-user totals including the empty-account case |
| Validation | Missing/blank fields, bad enums, over-long strings, invalid dates, `skip`/`limit` bounds, OpenAPI enum schema |

Each test gets a fresh in-memory database (`StaticPool`), so tests are isolated
and order-independent.

---

## Deployment: Neon + Render

Target topology: **PostgreSQL on Neon.tech** + **Web Service on Render**.

### Step 1 — Create the Neon database

1. Sign up at [neon.tech](https://neon.tech) and create a project. Pick the
   region closest to your Render region (e.g. `aws-us-east-1` / `aws-eu-central-1`).
2. Open **Connection Details** and copy the **pooled** connection string (the host
   contains `-pooler`). It looks like:

   ```
   postgresql://USER:PASSWORD@ep-cool-name-123456-pooler.us-east-2.aws.neon.tech/neondb?sslmode=require
   ```

3. Keep `sslmode=require` — Neon rejects unencrypted connections.
4. If the password contains `@`, `:`, `/` or `?`, percent-encode those characters.
5. No manual schema setup is required: the deploy runs `alembic upgrade head`.

> Use the pooled endpoint for a web service. It multiplexes connections, which
> keeps you well inside Neon's connection limits when Render scales.

### Step 2 — Create the Render Web Service

1. Push this repository to GitHub/GitLab.
2. In the Render dashboard: **New → Web Service**, connect the repository.
3. Configure:

   | Setting | Value |
   | --- | --- |
   | Runtime | `Python 3` |
   | Root Directory | `PrepTrack` |
   | Build Command | `pip install -r requirements.txt` |
   | Start Command | `alembic upgrade head && uvicorn main:app --host 0.0.0.0 --port $PORT` |
   | Health Check Path | `/health` |
   | Instance Type | Free (spins down after idle) or Starter |

   `--port $PORT` is mandatory: Render assigns the port at runtime and blocks
   traffic to anything else. Do **not** hardcode `8000`.
4. Add environment variables under **Environment → Environment Variables**:

   | Key | Value |
   | --- | --- |
   | `DATABASE_URL` | The pooled Neon URL from Step 1 |
   | `SECRET_KEY` | Output of `python -c "import secrets; print(secrets.token_urlsafe(48))"` |
   | `ENVIRONMENT` | `production` |
   | `ACCESS_TOKEN_EXPIRE_MINUTES` | `60` |
   | `PYTHON_VERSION` | `3.11.9` (optional pin; 3.10+ works) |

   `DATABASE_URL` may be pasted as `postgres://…` — the app rewrites it to
   `postgresql://` automatically.

5. Click **Deploy**. In the deploy log you should see
   `Running upgrade  -> 0001_initial, Initial schema`.

### Step 3 — Verify the deployment

```bash
curl https://YOUR-SERVICE.onrender.com/health          # {"status":"ok"}
open  https://YOUR-SERVICE.onrender.com/docs           # Swagger UI

curl -X POST https://YOUR-SERVICE.onrender.com/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email":"you@example.com","password":"StrongPass123!"}'
```

Then confirm in the Neon SQL editor:

```sql
select table_name from information_schema.tables
where table_schema = 'public';        -- users, problems, alembic_version
```

### Migrations on subsequent deploys

The start command runs `alembic upgrade head` on every boot, so new revisions
apply automatically. To run them manually, open **Render → Shell**:

```bash
alembic current
alembic upgrade head
alembic downgrade -1     # roll back one revision if needed
```

### Container deploy (alternative)

Render can build the included `Dockerfile` instead of the native Python runtime
(choose **Docker** as the environment). The image already runs
`alembic upgrade head` and binds `${PORT}`, so only the environment variables
need to be set. `docker-compose.yml` is for local development only and is not
used by Render.

---

## Operations & security checklist

- [ ] `SECRET_KEY` is a 48+ byte random value, unique per environment, stored
      only in Render's environment (never committed).
- [ ] `ENVIRONMENT=production` so the app refuses to boot without a secret.
- [ ] `DATABASE_URL` uses the Neon **pooled** endpoint with `sslmode=require`.
- [ ] HTTPS only — Render terminates TLS; tokens are bearer credentials.
- [ ] `*.db`, `.env*` and `__pycache__/` are git-ignored (see `.gitignore`).
- [ ] `/docs` left public for evaluation; disable it in `main.py`
      (`docs_url=None`) if the API should not advertise itself.
- [ ] Rotate `SECRET_KEY` to invalidate every issued token (all users re-login).
- [ ] Neon: enable **point-in-time restore** / take a branch before large changes.
- [ ] Monitor: Render logs + `/health`; Neon dashboard for connection counts and
      slow queries.
- [ ] Connection hygiene: `pool_pre_ping=True` and `pool_recycle=1800` are set,
      so suspended Neon computes do not surface stale-connection errors.

**Known limitations:** access tokens cannot be revoked before `exp` (stateless
JWTs); there is no refresh-token rotation, email verification or rate limiting —
add these before exposing the API to untrusted clients at scale.

---

## Troubleshooting

| Symptom | Cause / fix |
| --- | --- |
| `RuntimeError: SECRET_KEY environment variable must be set in production` | Expected in `ENVIRONMENT=production`; add `SECRET_KEY` to the environment. |
| `ModuleNotFoundError: No module named 'main'` on Render | Root Directory is not `PrepTrack`, or the start command omits `main:app`. |
| `could not connect to server` / SSL errors on Neon | Use the pooled URL and keep `?sslmode=require`; URL-encode special characters in the password. |
| `relation "problems" does not exist` | Migrations did not run: check the start command contains `alembic upgrade head`. |
| First request after idle takes ~30s | Render free instances sleep and Neon free computes suspend; both cold-start by design. |
| `422` on login | `/auth/login` expects **form** data (`username`, `password`), not JSON. |
| `401` on every call | Token expired or `SECRET_KEY` changed; log in again. |
| `alembic check` reports drift | You changed models without generating a revision: `alembic revision --autogenerate -m "..."`. |
| Tests fail with an unexpected database | Ensure `DATABASE_URL` is not exported to a production URL; tests always use in-memory SQLite. |
