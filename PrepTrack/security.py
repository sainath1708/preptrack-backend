"""Password hashing and JWT access-token helpers."""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from typing import Any

import jwt
from passlib.context import CryptContext

ALGORITHM = "HS256"
DEFAULT_DEV_SECRET = "dev-only-insecure-secret-do-not-use-in-production"

ENVIRONMENT = os.getenv("ENVIRONMENT", "development").strip().lower()

SECRET_KEY = os.getenv("SECRET_KEY", "").strip()
if not SECRET_KEY:
    if ENVIRONMENT in {"production", "prod"}:
        raise RuntimeError("SECRET_KEY environment variable must be set in production")
    SECRET_KEY = DEFAULT_DEV_SECRET

try:
    ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "60"))
except ValueError as exc:  # pragma: no cover - misconfiguration guard
    raise RuntimeError("ACCESS_TOKEN_EXPIRE_MINUTES must be an integer") from exc

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(plain_password: str) -> str:
    """Return a bcrypt hash for ``plain_password``."""
    return pwd_context.hash(plain_password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Constant-time comparison of a candidate password against a bcrypt hash."""
    try:
        return pwd_context.verify(plain_password, hashed_password)
    except (ValueError, TypeError):
        # Malformed hash or over-long password: treat as a failed login.
        return False


def create_access_token(
    subject: str | int,
    expires_delta: timedelta | None = None,
) -> str:
    """Sign a short-lived JWT whose ``sub`` claim is the user id."""
    now = datetime.now(timezone.utc)
    expire = now + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    payload: dict[str, Any] = {
        "sub": str(subject),
        "iat": now,
        "exp": expire,
        "type": "access",
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def decode_access_token(token: str) -> dict[str, Any]:
    """Verify signature/expiry and return the claims.

    Raises:
        jwt.InvalidTokenError: for expired, malformed or tampered tokens.
    """
    payload: dict[str, Any] = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    if payload.get("type") != "access":
        raise jwt.InvalidTokenError("unexpected token type")
    return payload
