"""
Admin authentication endpoints — login, refresh, me, change password, logout.
"""

import re
import time
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select

from app.database import get_session_context
from app.models.models import AdminUser
from app.services.admin_auth_service import (
    create_access_token,
    create_refresh_token,
    decode_token,
    decode_token_full,
    hash_password,
    verify_password,
)
from app.services.redis_cache import redis_cache
from app.utils.admin_deps import get_client_ip, get_current_admin

# Dummy bcrypt hash used to equalize timing when the username does not exist.
# This prevents attackers from distinguishing "user not found" (fast) from
# "wrong password" (slow ~100 ms bcrypt) via response-time analysis.
_DUMMY_HASH = "$2b$12$L.7IwIq4mxgqeSZi7PjmSuHJL2a.rQG5XbOdi/n1I023KV/y/zGOO"

security = HTTPBearer()

router = APIRouter(prefix="/auth", tags=["Admin Auth"])


class LoginRequest(BaseModel):
    username: str = Field(..., min_length=1)
    password: str = Field(..., min_length=1)


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshRequest(BaseModel):
    refresh_token: str


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(..., min_length=1)
    new_password: str = Field(..., min_length=8)

    @field_validator("new_password")
    @classmethod
    def password_complexity(cls, v: str) -> str:
        if not re.search(r"[A-Z]", v):
            raise ValueError(
                "La contraseña debe contener al menos una letra mayúscula"
            )
        if not re.search(r"[a-z]", v):
            raise ValueError(
                "La contraseña debe contener al menos una letra minúscula"
            )
        if not re.search(r"\d", v):
            raise ValueError(
                "La contraseña debe contener al menos un número"
            )
        return v


class LogoutRequest(BaseModel):
    refresh_token: str | None = None


class AdminMeResponse(BaseModel):
    id: int
    username: str
    rol: str
    activo: bool
    ultimo_login: datetime | None

    class Config:
        from_attributes = True


@router.post("/login", response_model=TokenResponse)
async def login(body: LoginRequest, request: Request):
    # Rate limit: max 5 attempts per IP in 15 minutes
    ip = get_client_ip(request)
    allowed, attempts = await redis_cache.check_login_rate_limit(ip)
    if not allowed:
        detail = (
            "Servicio temporalmente no disponible. Intenta en unos minutos."
            if attempts == -1
            else "Demasiados intentos de login. Intenta en 15 minutos."
        )
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=detail,
        )

    async with get_session_context() as session:
        result = await session.execute(
            select(AdminUser).where(AdminUser.username == body.username)
        )
        user = result.scalar_one_or_none()

        # Always run bcrypt verification to prevent timing side-channel.
        # When the user doesn't exist we verify against a dummy hash so the
        # response time is indistinguishable from a real password check.
        password_hash = user.password_hash if user is not None else _DUMMY_HASH
        password_ok = verify_password(body.password, password_hash)

        # Reject with the same generic error for all failure modes:
        # unknown user, wrong password, or deactivated account.
        if user is None or not password_ok or not user.activo:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Credenciales incorrectas",
            )
        user.ultimo_login = datetime.now(timezone.utc)

    # Clear rate limit on successful login
    await redis_cache.clear_login_attempts(ip)

    tenant_id = getattr(user, "tenant_id", None)
    return TokenResponse(
        access_token=create_access_token(user.username, tenant_id=tenant_id),
        refresh_token=create_refresh_token(user.username, tenant_id=tenant_id),
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(body: RefreshRequest, request: Request):
    # Rate limit refresh attempts
    ip = get_client_ip(request)
    allowed, attempts = await redis_cache.check_refresh_rate_limit(ip)
    if not allowed:
        detail = (
            "Servicio temporalmente no disponible. Intenta en unos minutos."
            if attempts == -1
            else "Demasiados intentos de refresh. Intenta en 15 minutos."
        )
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=detail,
        )

    _refresh_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Refresh token invalido o expirado",
    )

    # Decode and validate the old refresh token
    old_payload = decode_token_full(body.refresh_token)
    if old_payload is None or old_payload.get("type") != "refresh":
        raise _refresh_error

    username = old_payload["sub"]
    old_jti = old_payload.get("jti")

    # Check if the old refresh token is blacklisted
    if old_jti:
        if await redis_cache.is_token_blacklisted(old_jti):
            raise _refresh_error

    # Check if user's tokens were bulk-invalidated
    old_iat = old_payload.get("iat")
    if old_iat:
        invalidated_at = await redis_cache.get_user_tokens_invalidated_at(username)
        if invalidated_at and old_iat < invalidated_at:
            raise _refresh_error

    # Verify user still exists and is active
    async with get_session_context() as session:
        result = await session.execute(
            select(AdminUser).where(
                AdminUser.username == username,
                AdminUser.activo.is_(True),
            )
        )
        user = result.scalar_one_or_none()
        if user is None:
            raise _refresh_error

    # Blacklist the old refresh token (rotation)
    if old_jti:
        ttl = int(old_payload["exp"] - time.time())
        if ttl > 0:
            await redis_cache.blacklist_token(old_jti, ttl)

    tenant_id = old_payload.get("tenant_id")
    return TokenResponse(
        access_token=create_access_token(username, tenant_id=tenant_id),
        refresh_token=create_refresh_token(username, tenant_id=tenant_id),
    )


@router.get("/me", response_model=AdminMeResponse)
async def get_me(admin: AdminUser = Depends(get_current_admin)):
    return admin


@router.post("/change-password")
async def change_password(
    body: ChangePasswordRequest,
    request: Request,
    admin: AdminUser = Depends(get_current_admin),
):
    # Rate limit: max 3 password changes per hour per user
    ip = get_client_ip(request)
    rl_key = f"pwd_change:{admin.username}:{ip}"
    allowed, pwd_attempts = await redis_cache.check_refresh_rate_limit(rl_key, max_attempts=3, window_seconds=3600)
    if not allowed:
        detail = (
            "Servicio temporalmente no disponible. Intenta en unos minutos."
            if pwd_attempts == -1
            else "Demasiados intentos de cambio de contrasena. Intenta en 1 hora."
        )
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=detail,
        )

    async with get_session_context() as session:
        result = await session.execute(
            select(AdminUser).where(AdminUser.id == admin.id)
        )
        user = result.scalar_one()
        if not verify_password(body.current_password, user.password_hash):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Contrasena actual incorrecta",
            )
        user.password_hash = hash_password(body.new_password)

    # Invalidate all existing tokens for this user
    await redis_cache.invalidate_user_tokens(admin.username)

    return {"detail": "Contrasena actualizada"}


@router.post("/logout")
async def logout(
    body: LogoutRequest,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    current_user: AdminUser = Depends(get_current_admin),
):
    """Logout: blacklist the access token and optionally the refresh token."""
    # Blacklist the access token
    access_payload = decode_token_full(credentials.credentials)
    if access_payload and access_payload.get("jti"):
        ttl = int(access_payload["exp"] - time.time())
        if ttl > 0:
            await redis_cache.blacklist_token(access_payload["jti"], ttl)

    # Blacklist the refresh token if provided
    if body.refresh_token:
        refresh_payload = decode_token_full(body.refresh_token)
        if refresh_payload and refresh_payload.get("jti"):
            ttl = int(refresh_payload["exp"] - time.time())
            if ttl > 0:
                await redis_cache.blacklist_token(refresh_payload["jti"], ttl)

    return {"detail": "Sesion cerrada"}
