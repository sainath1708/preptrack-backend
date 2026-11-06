"""Authentication routes: registration, login and current-user lookup."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm

from crud import authenticate_user, create_user, get_user_by_email
from deps import CurrentUser, DbSession
from models import User
from schemas import Token, UserCreate, UserRead
from security import ACCESS_TOKEN_EXPIRE_MINUTES, create_access_token

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post(
    "/register",
    response_model=UserRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create an account",
    responses={409: {"description": "Email already registered"}},
)
def register(payload: UserCreate, db: DbSession) -> User:
    """Register a new user. The password is stored as a bcrypt hash only."""
    if get_user_by_email(db, payload.email) is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A user with this email already exists.",
        )

    # ConflictError from a concurrent insert is rendered as 409 by main.py.
    return create_user(db, payload)


@router.post(
    "/login",
    response_model=Token,
    summary="Exchange credentials for a JWT access token",
    responses={401: {"description": "Incorrect email or password"}},
)
def login(
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    db: DbSession,
) -> Token:
    """OAuth2 password flow. Send ``username`` (the email) and ``password`` as form data."""
    user = authenticate_user(db, form_data.username, form_data.password)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return Token(
        access_token=create_access_token(user.id),
        token_type="bearer",
        expires_in=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


@router.get(
    "/me",
    response_model=UserRead,
    summary="Return the authenticated user",
    responses={401: {"description": "Missing or invalid token"}},
)
def read_current_user(current_user: CurrentUser) -> User:
    """Cheap token-validity probe that also confirms the account still exists."""
    return current_user
