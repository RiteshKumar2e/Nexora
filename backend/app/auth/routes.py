"""Auth API routes — register, login, logout, me."""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import User
from app.auth.service import (
    authenticate_user,
    create_access_token,
    create_refresh_token,
    create_user,
    get_user_by_email,
    get_user_by_id,
    verify_token,
)
from app.db.session import get_db

router = APIRouter(prefix="/auth", tags=["auth"])


# ── Schemas ──────────────────────────────────────────────────

class RegisterRequest(BaseModel):
    email: str = Field(min_length=3, max_length=255)
    username: str = Field(min_length=2, max_length=100)
    password: str = Field(min_length=6, max_length=128)
    display_name: str | None = None


class LoginRequest(BaseModel):
    email: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: "UserResponse"


class UserResponse(BaseModel):
    id: str
    email: str
    username: str
    display_name: str | None


# ── Dependency ───────────────────────────────────────────────

async def get_current_user_optional(
    db: AsyncSession = Depends(get_db),
    authorization: str | None = None,
) -> User | None:
    """Extract user from Authorization header if present. Returns None for unauthenticated."""
    if not authorization or not authorization.startswith("Bearer "):
        return None
    token = authorization[7:]
    payload = verify_token(token)
    if payload is None or payload.get("type") != "access":
        return None
    try:
        user_id = uuid.UUID(payload["sub"])
    except (ValueError, KeyError):
        return None
    return await get_user_by_id(db, user_id)


# ── Routes ───────────────────────────────────────────────────

@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register(body: RegisterRequest, db: AsyncSession = Depends(get_db)):
    existing = await get_user_by_email(db, body.email)
    if existing:
        raise HTTPException(status.HTTP_409_CONFLICT, "Email already registered")
    user = await create_user(
        db,
        email=body.email,
        username=body.username,
        password=body.password,
        display_name=body.display_name,
    )
    return TokenResponse(
        access_token=create_access_token(str(user.id)),
        refresh_token=create_refresh_token(str(user.id)),
        user=UserResponse(
            id=str(user.id),
            email=user.email,
            username=user.username,
            display_name=user.display_name,
        ),
    )


@router.post("/login", response_model=TokenResponse)
async def login(body: LoginRequest, db: AsyncSession = Depends(get_db)):
    user = await authenticate_user(db, body.email, body.password)
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid credentials")
    return TokenResponse(
        access_token=create_access_token(str(user.id)),
        refresh_token=create_refresh_token(str(user.id)),
        user=UserResponse(
            id=str(user.id),
            email=user.email,
            username=user.username,
            display_name=user.display_name,
        ),
    )


@router.get("/me", response_model=UserResponse)
async def me(db: AsyncSession = Depends(get_db), authorization: str | None = None):
    user = await get_current_user_optional(db, authorization)
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Not authenticated")
    return UserResponse(
        id=str(user.id),
        email=user.email,
        username=user.username,
        display_name=user.display_name,
    )
