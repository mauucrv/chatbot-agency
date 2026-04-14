"""
Admin authentication service — JWT token creation/verification and password hashing.
"""

import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

import jwt
from jwt.exceptions import PyJWTError
from passlib.context import CryptContext

from app.config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30
REFRESH_TOKEN_EXPIRE_DAYS = 7


def hash_password(password: str) -> str:
    # bcrypt silently truncates passwords longer than 72 bytes
    return pwd_context.hash(password[:72])


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password[:72], hashed_password)


MAX_JWT_SIZE = 4096  # 4KB — our tokens are ~300 bytes


def create_access_token(subject: str, tenant_id: Optional[int] = None) -> str:
    now = datetime.now(timezone.utc)
    expire = now + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {
        "sub": subject,
        "exp": int(expire.timestamp()),
        "type": "access",
        "iat": int(now.timestamp()),
        "jti": str(uuid.uuid4()),
        "tenant_id": tenant_id,
    }
    return jwt.encode(
        payload,
        settings.secret_key,
        algorithm=ALGORITHM,
    )


def create_refresh_token(subject: str, tenant_id: Optional[int] = None) -> str:
    now = datetime.now(timezone.utc)
    expire = now + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    payload = {
        "sub": subject,
        "exp": int(expire.timestamp()),
        "type": "refresh",
        "iat": int(now.timestamp()),
        "jti": str(uuid.uuid4()),
        "tenant_id": tenant_id,
    }
    return jwt.encode(
        payload,
        settings.secret_key,
        algorithm=ALGORITHM,
    )


def decode_token_full(token: str) -> dict | None:
    """Decode JWT and return full payload dict, or None if invalid."""
    if len(token) > MAX_JWT_SIZE:
        return None
    try:
        payload = jwt.decode(
            token,
            settings.secret_key,
            algorithms=[ALGORITHM],
            options={"require": ["exp", "sub"]},
        )
        if not payload.get("sub"):
            return None
        return payload
    except PyJWTError:
        return None


def decode_token(token: str, expected_type: str = "access") -> str | None:
    """Decode JWT token and return the subject (username). Returns None if invalid."""
    payload = decode_token_full(token)
    if payload is None:
        return None
    if payload.get("type") != expected_type:
        return None
    return payload.get("sub")
