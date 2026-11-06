"""PrepTrack API application factory and router wiring.

Schema creation is intentionally absent: Alembic owns migrations
(``alembic upgrade head``). See README.md for the deployment workflow.
"""

from __future__ import annotations

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

from crud import ConflictError
from routers import auth, problems

app = FastAPI(
    title="PrepTrack API",
    version="2.0.0",
    description=(
        "Multi-tenant REST API for tracking interview-preparation problems.\n\n"
        "Authenticate via `POST /auth/login` (OAuth2 password flow) and send the "
        "returned JWT as `Authorization: Bearer <token>`.\n\n"
        "Every problem endpoint is scoped to the authenticated user."
    ),
)


@app.exception_handler(ConflictError)
async def conflict_exception_handler(request: Request, exc: ConflictError) -> JSONResponse:
    """Translate unique-constraint violations raised in the data layer into 409."""
    return JSONResponse(
        status_code=status.HTTP_409_CONFLICT,
        content={"detail": str(exc)},
    )


app.include_router(auth.router)
app.include_router(problems.router)
app.include_router(problems.stats_router)


@app.get("/", tags=["Health"], summary="Service banner")
def root() -> dict[str, str]:
    return {"service": "PrepTrack API", "version": app.version, "docs": "/docs"}


@app.get("/health", tags=["Health"], summary="Liveness probe for Render")
def health() -> dict[str, str]:
    """Cheap, dependency-free probe used by Render's health check."""
    return {"status": "ok"}
