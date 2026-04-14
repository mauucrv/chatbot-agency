"""Tests for configuration validation."""

import os
import pytest
from unittest.mock import patch

from pydantic import ValidationError


class TestProductionValidation:
    """Production mode requires critical settings."""

    def _prod_env(self, **overrides):
        base = {
            "APP_ENV": "production",
            "DATABASE_URL": "postgresql+asyncpg://u:p@localhost/db",
            "SECRET_KEY": "a" * 32,  # pragma: allowlist secret
            "OPENAI_API_KEY": "test-key",  # pragma: allowlist secret
            "CHATWOOT_BASE_URL": "http://test",
            "CHATWOOT_API_TOKEN": "test-token",
            "CHATWOOT_WEBHOOK_TOKEN": "test-token",
            "GOOGLE_CALENDAR_ID": "test@group.calendar.google.com",
            "REDIS_URL": "redis://:testpassword@redis:6379/0",
        }
        base.update(overrides)
        return base

    def test_production_requires_redis_password(self):
        env = self._prod_env(REDIS_URL="redis://localhost:6379/0")
        with patch.dict(os.environ, env, clear=False):
            from app.config import Settings
            with pytest.raises(ValidationError):
                Settings()

    def test_production_rejects_empty_redis_password(self):
        env = self._prod_env(REDIS_URL="redis://:@redis:6379/0")
        with patch.dict(os.environ, env, clear=False):
            from app.config import Settings
            with pytest.raises(ValidationError):
                Settings()

    def test_production_requires_database_url(self):
        env = self._prod_env(DATABASE_URL="")
        with patch.dict(os.environ, env, clear=False):
            from app.config import Settings
            with pytest.raises(ValidationError):
                Settings()

    def test_production_requires_secret_key(self):
        env = self._prod_env(SECRET_KEY="")
        with patch.dict(os.environ, env, clear=False):
            from app.config import Settings
            with pytest.raises(ValidationError):
                Settings()

    def test_production_requires_openai_key(self):
        env = self._prod_env(OPENAI_API_KEY="")
        with patch.dict(os.environ, env, clear=False):
            from app.config import Settings
            with pytest.raises(ValidationError):
                Settings()

    def test_production_requires_chatwoot_config(self):
        env = self._prod_env(CHATWOOT_BASE_URL="")
        with patch.dict(os.environ, env, clear=False):
            from app.config import Settings
            with pytest.raises(ValidationError):
                Settings()

    def test_production_requires_google_calendar_id(self):
        env = self._prod_env(GOOGLE_CALENDAR_ID="")
        with patch.dict(os.environ, env, clear=False):
            from app.config import Settings
            with pytest.raises(ValidationError):
                Settings()

    def test_production_rejects_short_secret_key(self):
        env = self._prod_env(SECRET_KEY="too-short")
        with patch.dict(os.environ, env, clear=True):
            with pytest.raises(ValidationError, match="SECRET_KEY"):
                from app.config import Settings
                Settings()

    def test_production_valid_passes(self):
        env = self._prod_env()
        with patch.dict(os.environ, env, clear=False):
            from app.config import Settings
            s = Settings()
            assert s.is_production is True


class TestDevelopmentDefaults:
    """Development mode provides sensible defaults."""

    def test_development_has_defaults(self):
        with patch.dict(os.environ, {"APP_ENV": "development"}, clear=False):
            from app.config import Settings
            s = Settings()
            assert s.database_url != ""
            assert s.secret_key != ""

    def test_is_production_false_in_dev(self):
        with patch.dict(os.environ, {"APP_ENV": "development"}, clear=False):
            from app.config import Settings
            s = Settings()
            assert s.is_production is False


class TestTelegramConfig:
    """Telegram notification settings."""

    def test_telegram_enabled_when_both_set(self):
        with patch.dict(os.environ, {
            "APP_ENV": "development",
            "TELEGRAM_BOT_TOKEN": "123:ABC",
            "TELEGRAM_CHAT_ID": "-100123",
        }, clear=False):
            from app.config import Settings
            s = Settings()
            assert s.telegram_notifications_enabled is True

    def test_telegram_disabled_without_token(self):
        with patch.dict(os.environ, {
            "APP_ENV": "development",
            "TELEGRAM_BOT_TOKEN": "",
            "TELEGRAM_CHAT_ID": "-100123",
        }, clear=False):
            from app.config import Settings
            s = Settings()
            assert s.telegram_notifications_enabled is False

    def test_telegram_disabled_without_chat_id(self):
        with patch.dict(os.environ, {
            "APP_ENV": "development",
            "TELEGRAM_BOT_TOKEN": "123:ABC",
            "TELEGRAM_CHAT_ID": "",
        }, clear=False):
            from app.config import Settings
            s = Settings()
            assert s.telegram_notifications_enabled is False


class TestDefaultValues:
    """Default values for configurable settings."""

    def test_default_rate_limit(self):
        with patch.dict(os.environ, {"APP_ENV": "development"}, clear=False):
            from app.config import Settings
            s = Settings()
            assert s.rate_limit_max_messages == 30
            assert s.rate_limit_window_seconds == 3600

    def test_default_booking_constraints(self):
        with patch.dict(os.environ, {"APP_ENV": "development"}, clear=False):
            from app.config import Settings
            s = Settings()
            assert s.max_booking_days_ahead == 90
            assert s.max_active_appointments_per_user == 3
            assert s.max_attachment_size_bytes == 10_485_760
