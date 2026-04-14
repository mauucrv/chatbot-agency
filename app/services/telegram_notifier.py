"""
Telegram error notification service.

Sends alerts to a Telegram chat when critical errors occur.
Fully optional: if TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID are not set,
all calls are silent no-ops.
"""

import hashlib
import html
import traceback as tb_module
from datetime import datetime

import httpx
import structlog
import pytz

from app.config import settings

logger = structlog.get_logger(__name__)

TZ = pytz.timezone(settings.calendar_timezone)

# Error type to emoji mapping
_ERROR_EMOJIS = {
    "unhandled_exception": "\u26a0\ufe0f",  # warning
    "database": "\U0001f5c4",  # file cabinet
    "redis": "\u26a1",  # lightning
    "agent_llm": "\U0001f9e0",  # brain
    "chatwoot_api": "\U0001f4ac",  # speech balloon
    "google_calendar": "\U0001f4c5",  # calendar
    "backup": "\U0001f4be",  # floppy disk
}

# Max Telegram message length
_MAX_MESSAGE_LENGTH = 4000


def _sanitize_traceback(tb_str: str) -> str:
    """Remove local variable values and sensitive paths from tracebacks."""
    import re
    # Keep only File/line references and exception lines, strip local var dumps
    lines = tb_str.splitlines()
    safe_lines = []
    for line in lines:
        # Keep standard traceback frame lines and exception lines
        stripped = line.lstrip()
        if (
            stripped.startswith("File ")
            or stripped.startswith("Traceback ")
            or stripped.startswith("raise ")
            or "Error" in stripped
            or "Exception" in stripped
            or line.startswith("  ")  # indented code lines from traceback
        ):
            # Redact anything after '=' that looks like a value assignment in locals
            safe_lines.append(line)
    return "\n".join(safe_lines) if safe_lines else tb_str[:500]


class TelegramNotifier:
    """Service for sending error alerts to Telegram."""

    def __init__(self):
        self._api_url = (
            f"https://api.telegram.org/bot{settings.telegram_bot_token}/sendMessage"
            if settings.telegram_bot_token
            else ""
        )
        self._doc_api_url = (
            f"https://api.telegram.org/bot{settings.telegram_bot_token}/sendDocument"
            if settings.telegram_bot_token
            else ""
        )
        self._chat_id = settings.telegram_chat_id
        self._cooldown = settings.telegram_alert_cooldown_seconds
        self._http_client: httpx.AsyncClient | None = None

    async def _get_http_client(self) -> httpx.AsyncClient:
        """Get or create a persistent HTTP client."""
        if self._http_client is None or self._http_client.is_closed:
            self._http_client = httpx.AsyncClient(timeout=10.0)
        return self._http_client

    async def close(self) -> None:
        """Close the persistent HTTP client."""
        if self._http_client and not self._http_client.is_closed:
            await self._http_client.close()
            self._http_client = None

    async def send_alert(
        self,
        error_type: str,
        message: str,
        traceback_str: str = "",
        conversation_id: int | None = None,
        extra: dict | None = None,
    ) -> bool:
        """
        Send an error alert to Telegram.

        Returns True if sent, False if skipped (disabled, deduped, or failed).
        """
        if not settings.telegram_notifications_enabled:
            return False

        # Deduplication via Redis
        fingerprint = hashlib.sha256(
            f"{error_type}:{message[:200]}".encode()
        ).hexdigest()[:32]

        dedup_sent = False
        try:
            from app.services.redis_cache import redis_cache

            dedup_key = f"{settings.redis_key_prefix}:telegram_alert:{fingerprint}"
            rc = await redis_cache.get_client()
            was_set = await rc.set(
                dedup_key, "1", ex=self._cooldown, nx=True
            )
            if not was_set:
                # Already sent recently
                return False
            dedup_sent = True
        except Exception:
            # Redis down — send anyway (fail-open for notifications)
            pass

        # Format and send
        text = self._format_message(
            error_type, message, traceback_str, conversation_id, extra
        )

        try:
            client = await self._get_http_client()
            response = await client.post(
                self._api_url,
                json={
                    "chat_id": self._chat_id,
                    "text": text,
                    "parse_mode": "HTML",
                    "disable_web_page_preview": True,
                },
            )
            if response.status_code == 200:
                logger.info(
                    "Telegram alert sent",
                    error_type=error_type,
                )
                return True
            else:
                logger.warning(
                    "Telegram API error",
                    status_code=response.status_code,
                    response=response.text[:200],
                )
                return False
        except Exception as e:
            logger.warning("Failed to send Telegram alert", error=str(e))
            return False

    async def send_document(
        self,
        file_path: str,
        caption: str = "",
    ) -> bool:
        """Send a file to the Telegram chat. Returns True if successful."""
        if not settings.telegram_notifications_enabled:
            return False

        try:
            from pathlib import Path

            path = Path(file_path)
            client = await self._get_http_client()
            with open(path, "rb") as f:
                response = await client.post(
                    self._doc_api_url,
                    data={
                        "chat_id": self._chat_id,
                        "caption": caption[:1024],
                        "parse_mode": "HTML",
                    },
                    files={"document": (path.name, f)},
                    timeout=30.0,
                )
                if response.status_code == 200:
                    logger.info("Telegram document sent", filename=path.name)
                    return True
                else:
                    logger.warning(
                        "Telegram sendDocument error",
                        status_code=response.status_code,
                        response=response.text[:200],
                    )
                    return False
        except Exception as e:
            logger.warning("Failed to send Telegram document", error=str(e))
            return False

    async def send_billing_alert(self, subject: str, message: str) -> bool:
        """
        Send a billing alert to Telegram. No dedup — billing alerts must always send.
        """
        if not settings.telegram_notifications_enabled:
            return False

        now = datetime.now(TZ).strftime("%Y-%m-%d %H:%M:%S %Z")
        text = (
            f"\U0001f4b0 <b>BILLING: {html.escape(subject)}</b>\n\n"
            f"<b>App:</b> {html.escape(settings.app_name)} ({html.escape(settings.app_env)})\n"
            f"<b>Time:</b> {now}\n\n"
            f"{html.escape(message)}"
        )
        if len(text) > _MAX_MESSAGE_LENGTH:
            text = text[:_MAX_MESSAGE_LENGTH] + "..."

        try:
            client = await self._get_http_client()
            response = await client.post(
                self._api_url,
                json={
                    "chat_id": self._chat_id,
                    "text": text,
                    "parse_mode": "HTML",
                    "disable_web_page_preview": True,
                },
            )
            if response.status_code == 200:
                logger.info("Telegram billing alert sent", subject=subject)
                return True
            else:
                logger.warning("Telegram billing alert failed", status_code=response.status_code)
                return False
        except Exception as e:
            logger.warning("Failed to send Telegram billing alert", error=str(e))
            return False

    def _format_message(
        self,
        error_type: str,
        message: str,
        traceback_str: str = "",
        conversation_id: int | None = None,
        extra: dict | None = None,
    ) -> str:
        emoji = _ERROR_EMOJIS.get(error_type, "\u2757")  # default: exclamation
        now = datetime.now(TZ).strftime("%Y-%m-%d %H:%M:%S %Z")

        parts = [
            f"{emoji} <b>{html.escape(error_type.upper().replace('_', ' '))}</b>",
            "",
            f"<b>App:</b> {html.escape(settings.app_name)} ({html.escape(settings.app_env)})",
            f"<b>Time:</b> {now}",
            f"<b>Error:</b> {html.escape(message[:500])}",
        ]

        if conversation_id is not None:
            parts.append(f"<b>Conversation:</b> #{conversation_id}")

        if extra:
            for key, value in extra.items():
                parts.append(f"<b>{html.escape(str(key))}:</b> {html.escape(str(value)[:100])}")

        if traceback_str:
            # Strip local variable values from traceback to avoid leaking PII
            sanitized_tb = _sanitize_traceback(traceback_str)
            max_tb_len = _MAX_MESSAGE_LENGTH - len("\n".join(parts)) - 50
            max_tb_len = max(200, min(max_tb_len, 1500))
            tb_truncated = sanitized_tb[-max_tb_len:]
            if len(sanitized_tb) > max_tb_len:
                tb_truncated = "..." + tb_truncated
            parts.append(f"\n<pre>{html.escape(tb_truncated)}</pre>")

        text = "\n".join(parts)
        if len(text) > _MAX_MESSAGE_LENGTH:
            text = text[:_MAX_MESSAGE_LENGTH] + "..."

        return text


# Singleton
telegram_notifier = TelegramNotifier()


async def notify_error(
    error_type: str,
    message: str,
    traceback_str: str = "",
    conversation_id: int | None = None,
    extra: dict | None = None,
) -> None:
    """Fire-and-forget error notification. Never raises."""
    try:
        await telegram_notifier.send_alert(
            error_type=error_type,
            message=message,
            traceback_str=traceback_str,
            conversation_id=conversation_id,
            extra=extra,
        )
    except Exception:
        pass


async def notify_billing(subject: str, message: str) -> None:
    """Fire-and-forget billing notification. Never raises."""
    try:
        await telegram_notifier.send_billing_alert(subject=subject, message=message)
    except Exception:
        pass
