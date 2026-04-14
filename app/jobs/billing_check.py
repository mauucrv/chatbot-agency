"""
Billing check job: warns about expiring subscriptions, suspends expired tenants,
and deactivates tenants after the grace period.

Runs daily. Sends Telegram alerts at configurable warning thresholds (default: 7, 3, 1 days).
"""

import traceback
from datetime import datetime, timedelta

import pytz
import structlog
from sqlalchemy import select

from app.config import settings
from app.database import get_session_context
from app.models import Tenant, PlanTenant
from app.services.redis_cache import redis_cache
from app.services.telegram_notifier import notify_billing, notify_error

logger = structlog.get_logger(__name__)

TZ = pytz.timezone(settings.calendar_timezone)


def _parse_warning_days() -> list[int]:
    """Parse billing_warning_days config into sorted list of ints."""
    return sorted(
        [int(d.strip()) for d in settings.billing_warning_days.split(",") if d.strip()],
        reverse=True,
    )


async def check_billing() -> None:
    """
    Daily billing check for all active tenants.

    Logic:
    - Trial tenants: checks trial_ends_at
    - Active tenants: checks subscription_expires_at
    - Sends warnings at configured thresholds (deduped via Redis)
    - Suspends on expiry day
    - Deactivates after grace period
    """
    try:
        now = datetime.now(TZ)
        warning_days = _parse_warning_days()
        grace_days = settings.billing_grace_period_days

        async with get_session_context() as session:
            result = await session.execute(
                select(Tenant).where(
                    Tenant.activo == True,
                    Tenant.plan.in_([PlanTenant.TRIAL, PlanTenant.ACTIVE]),
                )
            )
            tenants = result.scalars().all()

            for tenant in tenants:
                # Determine which expiry date to use
                if tenant.plan == PlanTenant.TRIAL:
                    expires_at = tenant.trial_ends_at
                    plan_label = "Trial"
                else:
                    expires_at = tenant.subscription_expires_at
                    plan_label = "Suscripción"

                if not expires_at:
                    continue

                # Make timezone-aware if naive
                if expires_at.tzinfo is None:
                    expires_at = TZ.localize(expires_at)

                days_left = (expires_at - now).days

                # Warnings before expiry
                if days_left > 0:
                    for threshold in warning_days:
                        if days_left <= threshold:
                            dedup_key = f"{settings.redis_key_prefix}:billing_notified:{tenant.id}:{threshold}"
                            try:
                                rc = await redis_cache.get_client()
                                was_set = await rc.set(
                                    dedup_key, "1", ex=86400, nx=True
                                )
                                if was_set:
                                    await notify_billing(
                                        f"{plan_label} por vencer — {tenant.nombre}",
                                        f"Tenant: {tenant.nombre} (ID: {tenant.id})\n"
                                        f"Plan: {plan_label}\n"
                                        f"Vence: {expires_at.strftime('%Y-%m-%d')}\n"
                                        f"Días restantes: {days_left}",
                                    )
                                    logger.info(
                                        "Billing warning sent",
                                        tenant_id=tenant.id,
                                        days_left=days_left,
                                        threshold=threshold,
                                    )
                            except Exception as e:
                                logger.warning("Redis dedup failed for billing", error=str(e))
                            break  # Only send the most relevant threshold

                # Expired — suspend
                elif days_left <= 0 and tenant.plan != PlanTenant.SUSPENDED:
                    tenant.plan = PlanTenant.SUSPENDED
                    await notify_billing(
                        f"Tenant suspendido — {tenant.nombre}",
                        f"Tenant: {tenant.nombre} (ID: {tenant.id})\n"
                        f"Venció: {expires_at.strftime('%Y-%m-%d')}\n"
                        f"Periodo de gracia: {grace_days} días\n"
                        f"Se desactivará el: {(expires_at + timedelta(days=grace_days)).strftime('%Y-%m-%d')}",
                    )
                    logger.warning(
                        "Tenant suspended — subscription expired",
                        tenant_id=tenant.id,
                        expired_at=expires_at.isoformat(),
                    )

            # Check suspended tenants past grace period
            suspended_result = await session.execute(
                select(Tenant).where(
                    Tenant.activo == True,
                    Tenant.plan == PlanTenant.SUSPENDED,
                )
            )
            suspended_tenants = suspended_result.scalars().all()

            for tenant in suspended_tenants:
                expires_at = tenant.subscription_expires_at or tenant.trial_ends_at
                if not expires_at:
                    continue

                if expires_at.tzinfo is None:
                    expires_at = TZ.localize(expires_at)

                days_past = (now - expires_at).days
                if days_past >= grace_days:
                    tenant.activo = False
                    await notify_billing(
                        f"Tenant desactivado — {tenant.nombre}",
                        f"Tenant: {tenant.nombre} (ID: {tenant.id})\n"
                        f"Venció: {expires_at.strftime('%Y-%m-%d')}\n"
                        f"Periodo de gracia de {grace_days} días agotado.\n"
                        f"Bot desactivado. Requiere pago y reactivación manual.",
                    )
                    logger.warning(
                        "Tenant deactivated — grace period expired",
                        tenant_id=tenant.id,
                        days_past_expiry=days_past,
                    )

            await session.commit()

        logger.info("Billing check completed", tenants_checked=len(tenants))

    except Exception as e:
        logger.error("Billing check job failed", error=str(e))
        await notify_error(
            "billing",
            f"Billing check job failed: {str(e)}",
            traceback_str=traceback.format_exc(),
        )
