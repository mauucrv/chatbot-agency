"""
FastAPI dependencies for admin authentication and authorization.
"""

from typing import Optional

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select

from app.context import set_current_tenant_id
from app.database import get_session_context
from app.models.models import AdminUser, RolAdmin
from app.services.admin_auth_service import decode_token_full
from app.services.redis_cache import redis_cache

security = HTTPBearer()


async def get_current_admin(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> AdminUser:
    """Decode JWT and return the active AdminUser, or raise 401."""
    _auth_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Token invalido o expirado",
    )

    payload = decode_token_full(credentials.credentials)
    if not payload or payload.get("type") != "access":
        raise _auth_error

    username = payload["sub"]
    jti = payload.get("jti")
    iat = payload.get("iat")
    tenant_id = payload.get("tenant_id")

    # Check blacklist (only if token has jti — backward compat for old tokens)
    if jti:
        if await redis_cache.is_token_blacklisted(jti):
            raise _auth_error

    # Check if user's tokens were bulk-invalidated (password change)
    if iat:
        invalidated_at = await redis_cache.get_user_tokens_invalidated_at(username)
        if invalidated_at and iat < invalidated_at:
            raise _auth_error

    async with get_session_context() as session:
        query = select(AdminUser).where(
            AdminUser.username == username,
            AdminUser.activo.is_(True),
        )
        # Verify tenant_id matches if present in token and model has the column
        if tenant_id is not None and hasattr(AdminUser, "tenant_id"):
            query = query.where(AdminUser.tenant_id == tenant_id)
        result = await session.execute(query)
        user = result.scalar_one_or_none()
        if user is None:
            raise _auth_error
        # Detach from session so it can be used outside
        session.expunge(user)

    # Set tenant context for downstream request processing
    if tenant_id is not None:
        set_current_tenant_id(tenant_id)

    return user


async def require_admin_role(
    admin: AdminUser = Depends(get_current_admin),
) -> AdminUser:
    """Require the 'admin' role (or higher) for write operations. Viewers get 403."""
    if admin.rol not in (RolAdmin.ADMIN, RolAdmin.SUPERADMIN):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Se requiere rol de administrador para esta accion",
        )
    return admin


async def require_superadmin_role(
    admin: AdminUser = Depends(get_current_admin),
) -> AdminUser:
    """Require the 'superadmin' role for tenant management operations."""
    if admin.rol != RolAdmin.SUPERADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Se requiere rol de superadmin para esta accion",
        )
    return admin


def check_tenant_access(
    obj, admin: AdminUser, detail: str = "Recurso no encontrado"
):
    """Raise 404 if obj is None or belongs to a different tenant.

    Use after ``session.get(Model, id)`` to enforce tenant isolation —
    both "not found" and "belongs to another tenant" return the same 404.
    """
    if obj is None:
        raise HTTPException(status_code=404, detail=detail)
    if hasattr(obj, "tenant_id") and obj.tenant_id != admin.tenant_id:
        raise HTTPException(status_code=404, detail=detail)
    return obj


def get_client_ip(request: Request) -> str:
    """Extract client IP for rate limiting.

    Behind a reverse proxy (nginx/Traefik/Docker), the rightmost IP in
    X-Forwarded-For is the one added by our trusted proxy — the real client.
    An attacker can only spoof IPs to the *left* of the chain.
    """
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        # Rightmost IP = added by our reverse proxy = real client
        ips = [ip.strip() for ip in forwarded.split(",") if ip.strip()]
        return ips[-1] if ips else (request.client.host if request.client else "unknown")
    return request.client.host if request.client else "unknown"
