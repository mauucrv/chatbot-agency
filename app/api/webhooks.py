"""
Webhook endpoints for Chatwoot integration.
"""

import hashlib
import hmac
import structlog
from typing import Any, Dict, Optional

from fastapi import APIRouter, BackgroundTasks, Header, HTTPException, Path, Query, Request
from fastapi.responses import JSONResponse
from sqlalchemy import select

from app.config import settings
from app.context import set_current_tenant_id
from app.database import get_session_context
from app.models import Tenant
from app.schemas import ChatwootWebhookPayload
from app.services.message_processor import message_processor

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/webhooks", tags=["webhooks"])


def verify_webhook_auth(
    payload: bytes,
    signature: Optional[str] = None,
    token: Optional[str] = None,
) -> bool:
    """
    Verify webhook authentication using token or HMAC signature.

    Supports two auth methods:
    1. URL token: ?token=SECRET (for Chatwoot which doesn't support HMAC signing)
    2. HMAC signature: X-Chatwoot-Signature header (if webhook_secret is configured)

    In production, at least one method must be configured. In development,
    requests are allowed through if neither is configured.
    """
    # Method 1: URL token authentication
    if settings.chatwoot_webhook_token:
        if token and hmac.compare_digest(token, settings.chatwoot_webhook_token):
            return True
        # Token is configured but not provided or doesn't match
        if not settings.chatwoot_webhook_secret:
            # Token is the only auth method — fail
            return False

    # Method 2: HMAC signature authentication
    if settings.chatwoot_webhook_secret:
        if not signature:
            return False
        expected = hmac.new(
            settings.chatwoot_webhook_secret.encode(),
            payload,
            hashlib.sha256,
        ).hexdigest()
        return hmac.compare_digest(signature, expected)

    # No auth configured
    if settings.is_production:
        logger.error("Webhook authentication not configured in production — rejecting request")
        return False

    # Development: allow without auth
    return True


@router.post("/chatwoot/{tenant_slug}")
async def chatwoot_webhook_tenant(
    request: Request,
    background_tasks: BackgroundTasks,
    tenant_slug: str = Path(..., description="Tenant slug for routing"),
    token: Optional[str] = Query(None),
) -> JSONResponse:
    """
    Tenant-aware webhook endpoint.
    Each tenant gets their own URL: POST /api/webhooks/chatwoot/{tenant_slug}?token=SECRET
    """
    try:
        # Lookup tenant by slug
        async with get_session_context() as session:
            result = await session.execute(
                select(Tenant).where(Tenant.slug == tenant_slug, Tenant.activo == True)
            )
            tenant = result.scalar_one_or_none()

        if not tenant:
            logger.warning("Webhook received for unknown tenant", tenant_slug=tenant_slug)
            raise HTTPException(status_code=404, detail="Tenant not found")

        # Verify per-tenant webhook token
        if not tenant.webhook_token or not token or not hmac.compare_digest(token, tenant.webhook_token):
            logger.warning("Tenant webhook auth failed", tenant_slug=tenant_slug)
            raise HTTPException(status_code=401, detail="Unauthorized")

        # Parse payload
        try:
            payload_dict = await request.json()
            payload = ChatwootWebhookPayload(**payload_dict)
        except Exception as e:
            logger.error("Failed to parse webhook payload", error=str(e))
            raise HTTPException(status_code=400, detail="Invalid payload")

        logger.info(
            "Tenant webhook received",
            tenant_id=tenant.id,
            tenant_slug=tenant_slug,
            webhook_event=payload.event,
            conversation_id=payload.conversation.id if payload.conversation else None,
        )

        # Process webhook in background with tenant context
        background_tasks.add_task(process_webhook_background, payload, tenant.id)

        return JSONResponse(
            status_code=200,
            content={"status": "accepted", "event": payload.event},
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error handling tenant webhook", tenant_slug=tenant_slug, error=str(e))
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/chatwoot")
async def chatwoot_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    x_chatwoot_signature: Optional[str] = Header(None, alias="X-Chatwoot-Signature"),
    token: Optional[str] = Query(None),
) -> JSONResponse:
    """
    Legacy webhook endpoint (backward-compatible).
    Routes to the default tenant (id=1) for existing single-tenant setups.
    """
    try:
        # Get raw body for signature verification
        body = await request.body()

        # Verify webhook authentication (token or HMAC)
        if not verify_webhook_auth(body, x_chatwoot_signature, token):
            logger.warning("Webhook authentication failed")
            raise HTTPException(status_code=401, detail="Unauthorized")

        # Parse payload
        try:
            payload_dict = await request.json()
            payload = ChatwootWebhookPayload(**payload_dict)
        except Exception as e:
            logger.error("Failed to parse webhook payload", error=str(e))
            raise HTTPException(status_code=400, detail="Invalid payload")

        # Resolve default tenant
        default_tenant_id = await _get_default_tenant_id()

        logger.info(
            "Webhook received (legacy route)",
            tenant_id=default_tenant_id,
            webhook_event=payload.event,
            message_type=payload.message_type,
            conversation_id=payload.conversation.id if payload.conversation else None,
        )

        # Process webhook in background with default tenant
        background_tasks.add_task(process_webhook_background, payload, default_tenant_id)

        return JSONResponse(
            status_code=200,
            content={"status": "accepted", "event": payload.event},
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error handling webhook", error=str(e))
        raise HTTPException(status_code=500, detail="Internal server error")


# Cache the default tenant ID to avoid repeated DB lookups
_default_tenant_id_cache: Optional[int] = None


async def _get_default_tenant_id() -> int:
    """Get the default tenant ID (first tenant), cached after first lookup."""
    global _default_tenant_id_cache
    if _default_tenant_id_cache is not None:
        return _default_tenant_id_cache
    async with get_session_context() as session:
        result = await session.execute(
            select(Tenant.id).where(Tenant.activo == True).order_by(Tenant.id).limit(1)
        )
        tenant_id = result.scalar_one_or_none()
        if tenant_id is None:
            raise RuntimeError("No active tenant found — seed the database first")
        _default_tenant_id_cache = tenant_id
        return tenant_id


async def process_webhook_background(
    payload: ChatwootWebhookPayload, tenant_id: int
) -> None:
    """Process webhook in background with tenant context."""
    try:
        set_current_tenant_id(tenant_id)
        result = await message_processor.process_webhook(payload, tenant_id=tenant_id)
        logger.info("Webhook processed", tenant_id=tenant_id, result=result)
    except Exception as e:
        logger.error("Error processing webhook in background", tenant_id=tenant_id, error=str(e))
        import traceback
        from app.services.telegram_notifier import notify_error
        await notify_error(
            "unhandled_exception",
            f"Webhook background processing failed (tenant {tenant_id}): {str(e)}",
            traceback_str=traceback.format_exc(),
            conversation_id=payload.conversation.id if payload.conversation else None,
        )


