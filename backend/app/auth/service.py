"""Auth service — password hashing, JWT tokens, user management."""
from __future__ import annotations

import hashlib
import hmac
import json
import time
import uuid
from base64 import urlsafe_b64decode, urlsafe_b64encode

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import User
from app.core.config import settings


# ── Password Hashing (bcrypt-style using hashlib + PBKDF2) ───

def hash_password(password: str) -> str:
    """Hash a password using PBKDF2-HMAC-SHA256 with random salt."""
    salt = uuid.uuid4().hex
    dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 100_000)
    return f"pbkdf2:sha256:{salt}:{dk.hex()}"


def verify_password(password: str, hashed: str) -> bool:
    """Verify a password against its hash."""
    try:
        parts = hashed.split(":")
        if len(parts) != 4 or parts[0] != "pbkdf2":
            return False
        salt = parts[2]
        expected = parts[3]
        dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 100_000)
        return hmac.compare_digest(dk.hex(), expected)
    except Exception:
        return False


# ── JWT Tokens (minimal, no external library) ────────────────

def _b64encode(data: bytes) -> str:
    return urlsafe_b64encode(data).rstrip(b"=").decode()


def _b64decode(s: str) -> bytes:
    s += "=" * (4 - len(s) % 4)
    return urlsafe_b64decode(s)


def create_token(payload: dict, expires_in_seconds: int) -> str:
    """Create a JWT-like token (HS256)."""
    header = _b64encode(json.dumps({"alg": "HS256", "typ": "JWT"}).encode())
    payload["exp"] = int(time.time()) + expires_in_seconds
    payload["iat"] = int(time.time())
    body = _b64encode(json.dumps(payload).encode())
    message = f"{header}.{body}"
    sig = hmac.new(
        settings.jwt_secret_key.encode(), message.encode(), hashlib.sha256
    ).digest()
    return f"{message}.{_b64encode(sig)}"


def verify_token(token: str) -> dict | None:
    """Verify and decode a JWT token. Returns payload or None."""
    try:
        parts = token.split(".")
        if len(parts) != 3:
            return None
        message = f"{parts[0]}.{parts[1]}"
        sig = hmac.new(
            settings.jwt_secret_key.encode(), message.encode(), hashlib.sha256
        ).digest()
        if not hmac.compare_digest(sig, _b64decode(parts[2])):
            return None
        payload = json.loads(_b64decode(parts[1]))
        if payload.get("exp", 0) < time.time():
            return None
        return payload
    except Exception:
        return None


def create_access_token(user_id: str) -> str:
    return create_token(
        {"sub": user_id, "type": "access"},
        settings.jwt_access_token_expire_minutes * 60,
    )


def create_refresh_token(user_id: str) -> str:
    return create_token(
        {"sub": user_id, "type": "refresh"},
        settings.jwt_refresh_token_expire_days * 86400,
    )


# ── User CRUD ────────────────────────────────────────────────

async def create_user(
    db: AsyncSession,
    *,
    email: str,
    username: str,
    password: str,
    display_name: str | None = None,
) -> User:
    user = User(
        email=email.lower().strip(),
        username=username.strip(),
        hashed_password=hash_password(password),
        display_name=display_name,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


async def get_user_by_email(db: AsyncSession, email: str) -> User | None:
    result = await db.execute(select(User).where(User.email == email.lower().strip()))
    return result.scalar_one_or_none()


async def get_user_by_id(db: AsyncSession, user_id: uuid.UUID) -> User | None:
    return await db.get(User, user_id)


async def authenticate_user(db: AsyncSession, email: str, password: str) -> User | None:
    user = await get_user_by_email(db, email)
    if user is None or not verify_password(password, user.hashed_password):
        return None
    if not user.is_active:
        return None
    return user
