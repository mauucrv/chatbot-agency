"""Tests for Telegram error notification service."""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from app.services.telegram_notifier import TelegramNotifier, notify_error


class TestSendAlert:
    """TelegramNotifier.send_alert behavior."""

    @pytest.mark.asyncio
    async def test_disabled_when_no_config(self):
        with patch("app.services.telegram_notifier.settings") as s:
            s.telegram_notifications_enabled = False
            notifier = TelegramNotifier.__new__(TelegramNotifier)
            notifier._api_url = ""
            notifier._chat_id = ""
            notifier._cooldown = 300
            result = await notifier.send_alert("test_error", "Test message")
            assert result is False

    @pytest.mark.asyncio
    async def test_sends_on_success(self):
        notifier = TelegramNotifier.__new__(TelegramNotifier)
        notifier._api_url = "https://api.telegram.org/bot123:ABC/sendMessage"
        notifier._chat_id = "-100123"
        notifier._cooldown = 300

        # Mock Redis to allow (not deduped)
        mock_redis = MagicMock()
        mock_redis.client = AsyncMock()
        mock_redis.client.set = AsyncMock(return_value=True)  # NX succeeds

        # Mock httpx response
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_client_instance = AsyncMock()
        mock_client_instance.post = AsyncMock(return_value=mock_resp)

        # Set persistent client so _get_http_client returns the mock
        mock_client_instance.is_closed = False
        notifier._http_client = mock_client_instance

        with patch("app.services.telegram_notifier.settings") as s:
            s.telegram_notifications_enabled = True
            s.redis_key_prefix = "agencybot"
            s.app_name = "agencybot-bot"
            s.app_env = "test"
            s.calendar_timezone = "America/Mexico_City"
            with patch("app.services.redis_cache.redis_cache", mock_redis):
                result = await notifier.send_alert("test_error", "Test message")
                assert result is True
                mock_client_instance.post.assert_called_once()

    @pytest.mark.asyncio
    async def test_dedup_blocks_duplicate(self):
        notifier = TelegramNotifier.__new__(TelegramNotifier)
        notifier._api_url = "https://api.telegram.org/bot123:ABC/sendMessage"
        notifier._chat_id = "-100123"
        notifier._cooldown = 300

        # Mock Redis to reject (already deduped)
        mock_redis = MagicMock()
        mock_redis.client = AsyncMock()
        mock_redis.client.set = AsyncMock(return_value=False)  # NX fails

        with patch("app.services.telegram_notifier.settings") as s:
            s.telegram_notifications_enabled = True
            s.redis_key_prefix = "agencybot"
            with patch("app.services.redis_cache.redis_cache", mock_redis):
                result = await notifier.send_alert("test_error", "Test message")
                assert result is False

    @pytest.mark.asyncio
    async def test_redis_down_sends_anyway(self):
        """When Redis is down, notifications should still be sent (fail-open)."""
        notifier = TelegramNotifier.__new__(TelegramNotifier)
        notifier._api_url = "https://api.telegram.org/bot123:ABC/sendMessage"
        notifier._chat_id = "-100123"
        notifier._cooldown = 300

        # Mock Redis to raise (simulating Redis down)
        mock_redis = MagicMock()
        mock_redis.client = AsyncMock()
        mock_redis.client.set = AsyncMock(side_effect=Exception("Redis down"))

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_client_instance = AsyncMock()
        mock_client_instance.post = AsyncMock(return_value=mock_resp)

        # Set persistent client so _get_http_client returns the mock
        mock_client_instance.is_closed = False
        notifier._http_client = mock_client_instance

        with patch("app.services.telegram_notifier.settings") as s:
            s.telegram_notifications_enabled = True
            s.redis_key_prefix = "agencybot"
            s.app_name = "agencybot-bot"
            s.app_env = "test"
            s.calendar_timezone = "America/Mexico_City"
            with patch("app.services.redis_cache.redis_cache", mock_redis):
                result = await notifier.send_alert("test_error", "Test message")
                assert result is True

    @pytest.mark.asyncio
    async def test_notify_error_never_raises(self):
        """The fire-and-forget wrapper should never raise."""
        with patch("app.services.telegram_notifier.telegram_notifier") as mock:
            mock.send_alert = AsyncMock(side_effect=Exception("Boom"))
            # Should not raise
            await notify_error("test", "message")
