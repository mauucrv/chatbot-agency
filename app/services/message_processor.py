"""
Message processor service with rate limiting and message grouping.
"""

import asyncio
import re
import traceback
import structlog
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
import pytz

from app.config import settings
from app.context import set_current_tenant_id
from app.database import get_session_context
from app.models import ConversacionChatwoot, EstadisticasBot, KeywordHumano, Lead, EtapaLead, OrigenLead
from app.services.chatwoot import get_chatwoot_service
from app.services.openai_service import openai_service
from app.services.redis_cache import redis_cache
from app.agent import get_agent
from app.schemas import ChatwootWebhookPayload

logger = structlog.get_logger(__name__)

# Timezone
TZ = pytz.timezone(settings.calendar_timezone)


class MessageProcessor:
    """Service for processing incoming messages."""

    def __init__(self):
        """Initialize the message processor."""
        self.message_delay = settings.message_group_delay
        self.rate_limit_max = settings.rate_limit_max_messages
        self.rate_limit_window = settings.rate_limit_window_seconds
        self._processing_tasks: Dict[int, asyncio.Task] = {}

    @staticmethod
    def _sanitize_for_whatsapp(text: str) -> str:
        """Convert markdown formatting to WhatsApp-compatible formatting."""
        # Remove markdown headers (### Header → *Header*)
        text = re.sub(r"^#{1,6}\s+(.+)$", r"*\1*", text, flags=re.MULTILINE)
        # Convert **bold** to *bold* (WhatsApp single asterisk)
        text = re.sub(r"\*\*(.+?)\*\*", r"*\1*", text)
        return text

    async def process_webhook(
        self, payload: ChatwootWebhookPayload, tenant_id: int = 1
    ) -> Dict[str, Any]:
        """
        Process an incoming Chatwoot webhook.

        Args:
            payload: The webhook payload
            tenant_id: The tenant this webhook belongs to

        Returns:
            Processing result
        """
        event = payload.event
        set_current_tenant_id(tenant_id)

        if event == "message_created":
            return await self._handle_message_created(payload, tenant_id)
        elif event == "conversation_status_changed":
            return await self._handle_conversation_status_changed(payload, tenant_id)
        elif event == "conversation_created":
            return await self._handle_conversation_created(payload, tenant_id)
        else:
            logger.debug("Ignoring webhook event", event=event)
            return {"status": "ignored", "event": event}

    async def _handle_message_created(
        self, payload: ChatwootWebhookPayload, tenant_id: int
    ) -> Dict[str, Any]:
        """Handle a new message webhook."""
        chatwoot_svc = await get_chatwoot_service(tenant_id)

        # Skip outgoing messages and private notes
        if payload.message_type != "incoming":
            return {"status": "skipped", "reason": "not_incoming"}

        if payload.private:
            return {"status": "skipped", "reason": "private_message"}

        # Check if sender is an agent (human)
        if payload.sender and payload.sender.type == "user":
            # Human agent responded - pause the bot and add handoff label
            await self._pause_bot_for_conversation(
                payload.conversation.id,
                tenant_id=tenant_id,
                reason="Agente humano respondió",
                paused_by=payload.sender.name or "Agente",
                escalate_to_human=True,
            )
            return {"status": "skipped", "reason": "human_agent_message"}

        conversation = payload.conversation
        if not conversation:
            return {"status": "error", "reason": "no_conversation"}

        conversation_id = conversation.id
        contact = conversation.contact

        # Extract phone number
        phone_number = None
        if contact:
            phone_number = contact.phone_number or contact.identifier

        if not phone_number:
            # Try to extract from conversation meta
            meta = conversation.meta or {}
            sender_info = meta.get("sender", {})
            phone_number = sender_info.get("phone_number")

        if not phone_number:
            logger.warning("No phone number found", conversation_id=conversation_id)
            phone_number = f"unknown_{conversation_id}"

        # Get or create conversation record
        conv_record = await self._get_or_create_conversation(
            conversation_id=conversation_id,
            phone_number=phone_number,
            tenant_id=tenant_id,
            contact_name=contact.name if contact else None,
            contact_id=contact.id if contact else None,
        )

        # Check if bot is active for this conversation
        if not conv_record.bot_activo:
            logger.info(
                "Bot paused for conversation",
                conversation_id=conversation_id,
                reason=conv_record.motivo_pausa,
            )
            # Send throttled reassurance so the customer knows they're not ignored
            should_reply = await redis_cache.should_send_paused_reply(
                tenant_id, conversation_id, settings.paused_reply_cooldown_seconds
            )
            if should_reply:
                await chatwoot_svc.send_message(
                    conversation_id,
                    settings.bot_paused_message
                    or "Tu conversación está siendo atendida por un agente humano. "
                    "Por favor espera, te responderá pronto. 🙏",
                )
            return {"status": "skipped", "reason": "bot_paused"}

        # Check rate limit
        is_allowed, msg_count = await redis_cache.check_rate_limit(
            tenant_id, phone_number, self.rate_limit_max, self.rate_limit_window
        )

        if not is_allowed:
            if msg_count == -1:
                # Redis is down - fail-closed
                logger.error(
                    "Rate limiting unavailable (Redis down) - rejecting message",
                    phone=phone_number[-4:],
                )
                from app.services.telegram_notifier import notify_error
                await notify_error(
                    "redis",
                    f"Redis unavailable during rate limiting, phone ...{phone_number[-4:]}",
                )
                await chatwoot_svc.send_message(
                    conversation_id,
                    "Estamos experimentando problemas temporales. Por favor intenta de nuevo en unos minutos.",
                )
                return {"status": "service_unavailable", "reason": "redis_down"}
            else:
                logger.warning(
                    "Rate limit exceeded",
                    phone=phone_number[-4:],
                    count=msg_count,
                )
                await chatwoot_svc.send_message(
                    conversation_id,
                    settings.rate_limit_message
                    or "Has enviado muchos mensajes. Por favor espera un momento antes de continuar.",
                )
                # Notify owner (deduplicated per phone per window)
                if (
                    settings.rate_limit_notify_owner
                    and settings.owner_phone_number
                ):
                    should_notify = await redis_cache.mark_rate_limit_owner_notified(
                        tenant_id, phone_number, self.rate_limit_window
                    )
                    if should_notify:
                        asyncio.create_task(
                            self._notify_owner_rate_limit(phone_number, msg_count, tenant_id)
                        )
                return {"status": "rate_limited", "count": msg_count}

        # Process message content
        message_content, content_meta = await self._extract_message_content(payload, tenant_id)

        if not message_content:
            return {"status": "skipped", "reason": "no_content"}

        # Check for human keywords
        if await self._check_human_keywords(message_content, tenant_id):
            await self._pause_bot_for_conversation(
                conversation_id,
                tenant_id=tenant_id,
                reason="Cliente solicitó agente humano",
                escalate_to_human=True,
            )
            await chatwoot_svc.send_message(
                conversation_id,
                settings.handoff_message
                or "Entendido, te voy a comunicar con un agente humano. "
                "Por favor espera un momento, te atenderán pronto. 🙏",
            )
            return {"status": "transferred", "reason": "human_keyword"}

        # Track unique user for this tenant
        await redis_cache.track_unique_user(tenant_id, phone_number)

        # Add message to pending queue and schedule processing
        message_data = {
            "content": message_content,
            "timestamp": datetime.now(TZ).isoformat(),
            "message_id": payload.id,
            "has_audio": content_meta.get("has_audio", False),
            "has_image": content_meta.get("has_image", False),
        }

        await redis_cache.add_pending_message(
            tenant_id, conversation_id, message_data, ttl=60
        )

        # Schedule delayed processing
        await self._schedule_processing(
            conversation_id, phone_number, contact.name if contact else None,
            contact_id=contact.id if contact else None,
            tenant_id=tenant_id,
        )

        return {"status": "queued", "conversation_id": conversation_id}

    async def _schedule_processing(
        self,
        conversation_id: int,
        phone_number: str,
        client_name: Optional[str],
        contact_id: Optional[int] = None,
        tenant_id: int = 1,
    ) -> None:
        """Schedule message processing after a delay."""
        # Cancel existing task if any
        if conversation_id in self._processing_tasks:
            task = self._processing_tasks[conversation_id]
            if not task.done():
                task.cancel()

        # Create new task
        task = asyncio.create_task(
            self._delayed_process(
                conversation_id, phone_number, client_name, contact_id, tenant_id
            )
        )
        self._processing_tasks[conversation_id] = task

    async def _delayed_process(
        self,
        conversation_id: int,
        phone_number: str,
        client_name: Optional[str],
        contact_id: Optional[int] = None,
        tenant_id: int = 1,
    ) -> None:
        """Process messages after a delay to group quick messages."""
        try:
            # Restore tenant context in this new task
            set_current_tenant_id(tenant_id)
            chatwoot_svc = await get_chatwoot_service(tenant_id)

            # Wait for message grouping delay
            await asyncio.sleep(self.message_delay)

            # Try to acquire processing lock
            if not await redis_cache.set_processing_lock(tenant_id, conversation_id):
                logger.debug("Processing lock not acquired", conversation_id=conversation_id)
                return

            try:
                # Re-check if bot is still active (may have been paused during delay)
                async with get_session_context() as session:
                    result = await session.execute(
                        select(ConversacionChatwoot.bot_activo).where(
                            ConversacionChatwoot.chatwoot_conversation_id == conversation_id,
                            ConversacionChatwoot.tenant_id == tenant_id,
                        )
                    )
                    bot_activo = result.scalar_one_or_none()
                    if bot_activo is False:
                        logger.info(
                            "Bot was paused during message grouping delay, skipping",
                            conversation_id=conversation_id,
                        )
                        await redis_cache.clear_pending_messages(tenant_id, conversation_id)
                        return

                # Get all pending messages
                pending = await redis_cache.get_pending_messages(tenant_id, conversation_id)
                if not pending:
                    return

                # Clear pending messages
                await redis_cache.clear_pending_messages(tenant_id, conversation_id)

                # Combine messages
                combined_message = " ".join([m["content"] for m in pending])

                # Get conversation context
                context = await redis_cache.get_conversation_context(tenant_id, conversation_id)

                # Process with AI agent
                start_time = datetime.now()
                agent = get_agent()
                response, tokens_used = await agent.process_message(
                    message=combined_message,
                    chat_history=context,
                    client_phone=phone_number,
                    client_name=client_name,
                    conversation_id=conversation_id,
                    contact_id=contact_id,
                )
                processing_time = (datetime.now() - start_time).total_seconds() * 1000

                # Convert markdown formatting to WhatsApp-compatible formatting
                response = self._sanitize_for_whatsapp(response)

                # Send response
                await chatwoot_svc.send_message(conversation_id, response)

                # Update conversation context
                new_context = (context or []) + [
                    {"role": "user", "content": combined_message},
                    {"role": "assistant", "content": response},
                ]
                new_context = new_context[-settings.conversation_context_limit:]
                await redis_cache.set_conversation_context(
                    tenant_id, conversation_id, new_context, ttl=settings.conversation_context_ttl
                )

                # Collect media counts from pending messages
                audio_count = sum(1 for m in pending if m.get("has_audio"))
                image_count = sum(1 for m in pending if m.get("has_image"))

                # Update statistics with real token count from OpenAI API
                await self._update_statistics(
                    tenant_id=tenant_id,
                    mensajes_recibidos=len(pending),
                    mensajes_respondidos=1,
                    mensajes_audio=audio_count,
                    mensajes_imagen=image_count,
                    tokens_openai_aprox=tokens_used,
                    response_time_ms=processing_time,
                )

                logger.info(
                    "Messages processed",
                    tenant_id=tenant_id,
                    conversation_id=conversation_id,
                    message_count=len(pending),
                    processing_time_ms=processing_time,
                )

            finally:
                await redis_cache.release_processing_lock(tenant_id, conversation_id)

        except asyncio.CancelledError:
            logger.debug("Processing cancelled", conversation_id=conversation_id)
        except Exception as e:
            logger.error(
                "Error processing messages",
                tenant_id=tenant_id,
                conversation_id=conversation_id,
                error=str(e),
            )
            from app.services.telegram_notifier import notify_error
            await notify_error(
                "agent_llm",
                f"Error processing messages for conv {conversation_id} (tenant {tenant_id}): {str(e)}",
                traceback_str=traceback.format_exc(),
                conversation_id=conversation_id,
            )
            await self._update_statistics(tenant_id=tenant_id, errores=1)
        finally:
            # Clean up completed task to prevent memory leak
            self._processing_tasks.pop(conversation_id, None)

    async def _extract_message_content(
        self, payload: ChatwootWebhookPayload, tenant_id: int
    ) -> tuple[Optional[str], dict]:
        """Extract and process message content from payload.

        Returns:
            Tuple of (content_string, metadata_dict) where metadata contains
            counts of media types processed (has_audio, has_image).
        """
        chatwoot_svc = await get_chatwoot_service(tenant_id)
        parts = []
        meta = {"has_audio": False, "has_image": False}

        # Process text content
        if payload.content:
            parts.append(payload.content)

        # Process attachments
        if payload.attachments:
            for attachment in payload.attachments:
                if not attachment.data_url:
                    continue

                file_type = attachment.file_type or ""

                # Handle audio
                if file_type.startswith("audio") or attachment.extension in [
                    "ogg", "mp3", "wav", "m4a", "opus"
                ]:
                    meta["has_audio"] = True
                    audio_data = await chatwoot_svc.download_attachment(
                        attachment.data_url
                    )
                    if audio_data:
                        transcription = await openai_service.transcribe_audio(
                            audio_data,
                            filename=f"audio.{attachment.extension or 'ogg'}",
                        )
                        if transcription:
                            parts.append(f"[Audio transcrito]: {transcription}")
                        else:
                            parts.append(
                                "[El cliente envió un mensaje de voz pero no se pudo transcribir. "
                                "Pídele amablemente que escriba su mensaje.]"
                            )
                    else:
                        parts.append(
                            "[El cliente envió un mensaje de voz pero no se pudo descargar el audio. "
                            "Pídele amablemente que escriba su mensaje.]"
                        )

                # Handle images
                elif file_type.startswith("image") or attachment.extension in [
                    "jpg", "jpeg", "png", "gif", "webp"
                ]:
                    meta["has_image"] = True
                    image_data = await chatwoot_svc.download_attachment(
                        attachment.data_url
                    )
                    if image_data:
                        description = await openai_service.describe_image(image_data)
                        if description:
                            parts.append(f"[Imagen adjunta]: {description}")
                        else:
                            parts.append(
                                "[El cliente envió una imagen pero no se pudo analizar. "
                                "Pídele que describa lo que necesita.]"
                            )
                    else:
                        parts.append(
                            "[El cliente envió una imagen pero no se pudo descargar. "
                            "Pídele que describa lo que necesita.]"
                        )

        content = " ".join(parts) if parts else None
        return content, meta

    async def _handle_conversation_status_changed(
        self, payload: ChatwootWebhookPayload, tenant_id: int
    ) -> Dict[str, Any]:
        """Handle conversation status change webhook."""
        conversation = payload.conversation
        if not conversation:
            return {"status": "error", "reason": "no_conversation"}

        new_status = payload.status or conversation.status

        # If conversation is resolved, reactivate bot
        if new_status == "resolved":
            await self._reactivate_bot_for_conversation(conversation.id, tenant_id)
            return {"status": "bot_reactivated", "conversation_id": conversation.id}

        return {"status": "ok", "new_status": new_status}

    async def _handle_conversation_created(
        self, payload: ChatwootWebhookPayload, tenant_id: int
    ) -> Dict[str, Any]:
        """Handle new conversation webhook."""
        conversation = payload.conversation
        if not conversation:
            return {"status": "error", "reason": "no_conversation"}

        contact = conversation.contact
        phone_number = None
        if contact:
            phone_number = contact.phone_number or contact.identifier

        if not phone_number:
            phone_number = f"unknown_{conversation.id}"

        # Create conversation record
        await self._get_or_create_conversation(
            conversation_id=conversation.id,
            phone_number=phone_number,
            tenant_id=tenant_id,
            contact_name=contact.name if contact else None,
            contact_id=contact.id if contact else None,
        )

        return {"status": "created", "conversation_id": conversation.id}

    async def _get_or_create_conversation(
        self,
        conversation_id: int,
        phone_number: str,
        tenant_id: int = 1,
        contact_name: Optional[str] = None,
        contact_id: Optional[int] = None,
    ) -> ConversacionChatwoot:
        """Get or create a conversation record (tenant-scoped)."""
        async with get_session_context() as session:
            result = await session.execute(
                select(ConversacionChatwoot).where(
                    ConversacionChatwoot.chatwoot_conversation_id == conversation_id,
                    ConversacionChatwoot.tenant_id == tenant_id,
                )
            )
            conv = result.scalar_one_or_none()

            if conv:
                # Update last message timestamp
                conv.ultimo_mensaje_at = datetime.now(TZ)
                if contact_name and not conv.nombre_cliente:
                    conv.nombre_cliente = contact_name

                # Update lead's ultimo_contacto if exists
                if phone_number:
                    await session.execute(
                        update(Lead)
                        .where(Lead.telefono == phone_number, Lead.tenant_id == tenant_id)
                        .values(ultimo_contacto=datetime.now(TZ))
                    )

                await session.commit()
                return conv

            # Create new record
            conv = ConversacionChatwoot(
                chatwoot_conversation_id=conversation_id,
                chatwoot_contact_id=contact_id,
                telefono_cliente=phone_number,
                nombre_cliente=contact_name,
                bot_activo=True,
                ultimo_mensaje_at=datetime.now(TZ),
                tenant_id=tenant_id,
            )
            session.add(conv)

            # Auto-create CRM lead if one doesn't exist for this phone in this tenant
            if phone_number:
                existing_lead = await session.execute(
                    select(Lead).where(
                        Lead.telefono == phone_number,
                        Lead.tenant_id == tenant_id,
                    )
                )
                if not existing_lead.scalar_one_or_none():
                    lead = Lead(
                        nombre=contact_name,
                        telefono=phone_number,
                        etapa=EtapaLead.NUEVO,
                        origen=OrigenLead.WHATSAPP_ORGANICO,
                        chatwoot_conversation_id=conversation_id,
                        chatwoot_contact_id=contact_id,
                        ultimo_contacto=datetime.now(TZ),
                        tenant_id=tenant_id,
                    )
                    session.add(lead)
                    logger.info(
                        "CRM lead auto-created",
                        tenant_id=tenant_id,
                        phone=phone_number[-4:] if phone_number else None,
                    )

            await session.commit()
            await session.refresh(conv)

            logger.info(
                "Conversation record created",
                tenant_id=tenant_id,
                conversation_id=conversation_id,
                phone=phone_number[-4:] if phone_number else None,
            )

            return conv

    async def _pause_bot_for_conversation(
        self,
        conversation_id: int,
        tenant_id: int = 1,
        reason: str = "",
        paused_by: Optional[str] = None,
        escalate_to_human: bool = False,
    ) -> None:
        """Pause the bot for a conversation and optionally escalate in Chatwoot."""
        async with get_session_context() as session:
            await session.execute(
                update(ConversacionChatwoot)
                .where(
                    ConversacionChatwoot.chatwoot_conversation_id == conversation_id,
                    ConversacionChatwoot.tenant_id == tenant_id,
                )
                .values(
                    bot_activo=False,
                    motivo_pausa=reason,
                    pausado_por=paused_by,
                    pausado_en=datetime.now(TZ),
                )
            )
            await session.commit()

        # Clear conversation context and pending messages
        await redis_cache.clear_conversation_context(tenant_id, conversation_id)
        await redis_cache.clear_pending_messages(tenant_id, conversation_id)

        # Escalate in Chatwoot so the team sees it
        if escalate_to_human:
            await self._escalate_conversation(conversation_id, reason, tenant_id)

        logger.info(
            "Bot paused",
            tenant_id=tenant_id,
            conversation_id=conversation_id,
            reason=reason,
            escalated=escalate_to_human,
        )

        # Update statistics
        await self._update_statistics(tenant_id=tenant_id, transferencias_humano=1)

    async def _escalate_conversation(
        self, conversation_id: int, reason: str, tenant_id: int = 1
    ) -> None:
        """Escalate a conversation in Chatwoot: set status, add label, leave internal note."""
        chatwoot_svc = await get_chatwoot_service(tenant_id)

        # All Chatwoot calls are fire-and-forget: failures are logged but don't block
        try:
            await chatwoot_svc.update_conversation_status(
                conversation_id, settings.handoff_chatwoot_status
            )
        except Exception as e:
            logger.error("Failed to update conversation status on escalation", error=str(e))

        try:
            await chatwoot_svc.add_labels(
                conversation_id, [settings.handoff_label]
            )
        except Exception as e:
            logger.error("Failed to add handoff label", error=str(e))

        try:
            await chatwoot_svc.send_message(
                conversation_id,
                f"🔔 Handoff automático: {reason}",
                private=True,
            )
        except Exception as e:
            logger.error("Failed to send escalation private note", error=str(e))

    async def _reactivate_bot_for_conversation(
        self, conversation_id: int, tenant_id: int = 1
    ) -> None:
        """Reactivate the bot for a conversation."""
        async with get_session_context() as session:
            await session.execute(
                update(ConversacionChatwoot)
                .where(
                    ConversacionChatwoot.chatwoot_conversation_id == conversation_id,
                    ConversacionChatwoot.tenant_id == tenant_id,
                )
                .values(
                    bot_activo=True,
                    motivo_pausa=None,
                    pausado_por=None,
                    pausado_en=None,
                )
            )
            await session.commit()

        # Clear old conversation context and paused-reply cooldown
        await redis_cache.clear_conversation_context(tenant_id, conversation_id)
        await redis_cache.clear_paused_reply_cooldown(tenant_id, conversation_id)

        # Remove handoff label since bot is back in control
        chatwoot_svc = await get_chatwoot_service(tenant_id)
        try:
            await chatwoot_svc.remove_labels(conversation_id, [settings.handoff_label])
        except Exception as e:
            logger.error("Failed to remove handoff label on reactivation", error=str(e))

        logger.info("Bot reactivated", tenant_id=tenant_id, conversation_id=conversation_id)

    async def _check_human_keywords(self, message: str, tenant_id: int = 1) -> bool:
        """Check if message contains keywords that trigger human handoff (tenant-scoped).
        Uses word-boundary matching to avoid false positives
        (e.g. 'cooperador' no longer triggers 'operador').
        """
        # Get keywords from cache or database
        keywords = await redis_cache.get_keywords(tenant_id)

        if keywords is None:
            async with get_session_context() as session:
                result = await session.execute(
                    select(KeywordHumano).where(
                        KeywordHumano.activo == True,
                        KeywordHumano.tenant_id == tenant_id,
                    )
                )
                keyword_records = result.scalars().all()
                keywords = [k.keyword.lower() for k in keyword_records]
                await redis_cache.set_keywords(tenant_id, keywords)

        # Check message against keywords using word boundaries
        message_lower = message.lower()
        for keyword in keywords:
            pattern = r"\b" + re.escape(keyword) + r"\b"
            if re.search(pattern, message_lower):
                logger.info("Human keyword detected", keyword=keyword)
                return True

        return False

    async def _notify_owner_rate_limit(
        self, phone_number: str, msg_count: int, tenant_id: int = 1
    ) -> None:
        """Send a rate-limit alert to the salon owner via Chatwoot."""
        try:
            chatwoot_svc = await get_chatwoot_service(tenant_id)
            masked = f"***{phone_number[-4:]}" if len(phone_number) >= 4 else phone_number
            message = (
                f"[Alerta Bot] El número {masked} ha sido limitado "
                f"por exceder el límite de mensajes ({msg_count} mensajes)."
            )
            await chatwoot_svc.send_message_to_phone(
                settings.owner_phone_number, message
            )
            logger.info(
                "Owner notified of rate limit",
                phone=phone_number[-4:],
                count=msg_count,
            )
        except Exception as e:
            logger.error(
                "Failed to notify owner of rate limit",
                error=str(e),
                phone=phone_number[-4:],
            )

    async def _update_statistics(
        self,
        tenant_id: int = 1,
        mensajes_recibidos: int = 0,
        mensajes_respondidos: int = 0,
        mensajes_audio: int = 0,
        mensajes_imagen: int = 0,
        tokens_openai_aprox: int = 0,
        citas_creadas: int = 0,
        citas_modificadas: int = 0,
        citas_canceladas: int = 0,
        transferencias_humano: int = 0,
        errores: int = 0,
        response_time_ms: Optional[float] = None,
    ) -> None:
        """Update daily statistics (tenant-scoped)."""
        try:
            async with get_session_context() as session:
                today = datetime.now(TZ).replace(hour=0, minute=0, second=0, microsecond=0)

                result = await session.execute(
                    select(EstadisticasBot).where(
                        EstadisticasBot.fecha == today,
                        EstadisticasBot.tenant_id == tenant_id,
                    )
                )
                stats = result.scalar_one_or_none()

                # Get today's unique user count from Redis HyperLogLog
                today_str = datetime.now(TZ).strftime("%Y-%m-%d")
                unique_users = await redis_cache.get_unique_user_count(tenant_id, today_str)

                if stats:
                    stats.mensajes_recibidos += mensajes_recibidos
                    stats.mensajes_respondidos += mensajes_respondidos
                    stats.mensajes_audio += mensajes_audio
                    stats.mensajes_imagen += mensajes_imagen
                    stats.tokens_openai_aprox += tokens_openai_aprox
                    stats.usuarios_unicos = unique_users
                    stats.citas_creadas += citas_creadas
                    stats.citas_modificadas += citas_modificadas
                    stats.citas_canceladas += citas_canceladas
                    stats.transferencias_humano += transferencias_humano
                    stats.errores += errores

                    if response_time_ms:
                        if stats.tiempo_respuesta_promedio_ms:
                            # Calculate running average
                            total = stats.mensajes_respondidos
                            stats.tiempo_respuesta_promedio_ms = (
                                (stats.tiempo_respuesta_promedio_ms * (total - 1) + response_time_ms)
                                / total
                            )
                        else:
                            stats.tiempo_respuesta_promedio_ms = response_time_ms
                else:
                    stats = EstadisticasBot(
                        fecha=today,
                        mensajes_recibidos=mensajes_recibidos,
                        mensajes_respondidos=mensajes_respondidos,
                        mensajes_audio=mensajes_audio,
                        mensajes_imagen=mensajes_imagen,
                        tokens_openai_aprox=tokens_openai_aprox,
                        usuarios_unicos=unique_users,
                        citas_creadas=citas_creadas,
                        citas_modificadas=citas_modificadas,
                        citas_canceladas=citas_canceladas,
                        transferencias_humano=transferencias_humano,
                        errores=errores,
                        tiempo_respuesta_promedio_ms=response_time_ms,
                        tenant_id=tenant_id,
                    )
                    session.add(stats)

                await session.commit()

        except Exception as e:
            logger.error("Error updating statistics", error=str(e))


# Singleton instance
message_processor = MessageProcessor()
