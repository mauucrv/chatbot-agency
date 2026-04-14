"""
Auto-resume job: reactivates conversations that have been paused too long.

If a human agent intervenes but forgets to resolve the conversation,
the bot stays paused indefinitely. This job periodically checks for
conversations paused longer than `auto_resume_hours` and reactivates them.
"""

import traceback
from datetime import datetime, timedelta

import pytz
import structlog
from sqlalchemy import select, update

from app.config import settings
from app.database import get_session_context
from app.models import ConversacionChatwoot
from app.services.chatwoot import get_chatwoot_service
from app.services.redis_cache import redis_cache

logger = structlog.get_logger(__name__)

TZ = pytz.timezone(settings.calendar_timezone)


async def auto_resume_paused_conversations() -> None:
    """
    Find conversations paused for longer than `auto_resume_hours` and reactivate them.

    Mirrors the logic of MessageProcessor._reactivate_bot_for_conversation:
    - Sets bot_activo = True, clears pause metadata
    - Clears Redis conversation context and paused-reply cooldown
    - Removes the handoff label in Chatwoot
    """
    logger.info(
        "Starting auto-resume job",
        threshold_hours=settings.auto_resume_hours,
    )

    try:
        cutoff = datetime.now(TZ) - timedelta(hours=settings.auto_resume_hours)

        async with get_session_context() as session:
            # Find all conversations paused before the cutoff
            result = await session.execute(
                select(ConversacionChatwoot)
                .where(ConversacionChatwoot.bot_activo == False)
                .where(ConversacionChatwoot.pausado_en.isnot(None))
                .where(ConversacionChatwoot.pausado_en < cutoff)
            )
            stale_conversations = result.scalars().all()

            if not stale_conversations:
                logger.info("No stale paused conversations found")
                return

            resumed_count = 0
            failed_count = 0

            for conv in stale_conversations:
                conversation_id = conv.chatwoot_conversation_id
                tenant_id = conv.tenant_id or 1
                try:
                    # Reactivate in DB
                    await session.execute(
                        update(ConversacionChatwoot)
                        .where(
                            ConversacionChatwoot.chatwoot_conversation_id
                            == conversation_id,
                            ConversacionChatwoot.tenant_id == tenant_id,
                        )
                        .values(
                            bot_activo=True,
                            motivo_pausa=None,
                            pausado_por=None,
                            pausado_en=None,
                        )
                    )

                    # Clear Redis state
                    await redis_cache.clear_conversation_context(tenant_id, conversation_id)
                    await redis_cache.clear_paused_reply_cooldown(tenant_id, conversation_id)

                    # Remove handoff label in Chatwoot (fire-and-forget)
                    try:
                        chatwoot_svc = await get_chatwoot_service(tenant_id)
                        await chatwoot_svc.remove_labels(
                            conversation_id, [settings.handoff_label]
                        )
                    except Exception as e:
                        logger.warning(
                            "Failed to remove handoff label during auto-resume",
                            conversation_id=conversation_id,
                            error=str(e),
                        )

                    resumed_count += 1
                    logger.info(
                        "Auto-resumed conversation",
                        conversation_id=conversation_id,
                        paused_since=conv.pausado_en.isoformat() if conv.pausado_en else None,
                        paused_by=conv.pausado_por,
                    )

                except Exception as e:
                    failed_count += 1
                    logger.error(
                        "Failed to auto-resume conversation",
                        conversation_id=conversation_id,
                        error=str(e),
                    )

            await session.commit()

            logger.info(
                "Auto-resume job completed",
                total=len(stale_conversations),
                resumed=resumed_count,
                failed=failed_count,
            )

    except Exception as e:
        logger.error("Error in auto-resume job", error=str(e))
        from app.services.telegram_notifier import notify_error

        await notify_error(
            "database",
            f"Auto-resume job failed: {str(e)}",
            traceback_str=traceback.format_exc(),
        )
