"""Shared FastAPI dependencies (session + authenticated user)."""

from __future__ import annotations

from typing import Annotated

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from crud import get_user
from database import get_db
from models import User
from security import decode_access_token

# tokenUrl powers the Swagger "Authorize" button.
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")

credentials_exception = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Could not validate credentials",
    headers={"WWW-Authenticate": "Bearer"},
)

DbSession = Annotated[Session, Depends(get_db)]


def get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)],
    db: DbSession,
) -> User:
    """Resolve the bearer token to a persisted user or raise 401."""
    try:
        payload = decode_access_token(token)
        user_id = int(payload["sub"])
    except (jwt.InvalidTokenError, KeyError, TypeError, ValueError) as exc:
        raise credentials_exception from exc

    user = get_user(db, user_id)
    if user is None:
        # Token is valid but the account no longer exists.
        raise credentials_exception
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]
