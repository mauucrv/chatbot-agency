"""
Application configuration using Pydantic Settings.
"""

import base64
import json
from functools import lru_cache
from typing import Optional

import structlog
from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = structlog.get_logger(__name__)


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Application
    app_name: str = Field(default="agencybot-bot")
    app_env: str = Field(default="development")
    debug: bool = Field(default=False)
    log_level: str = Field(default="INFO")

    # Server
    host: str = Field(default="0.0.0.0")
    port: int = Field(default=8000)

    # Database - no default password
    database_url: str = Field(default="")

    # Redis
    redis_url: str = Field(default="redis://localhost:6379/0")
    cache_ttl_services: int = Field(default=3600)
    cache_ttl_stylists: int = Field(default=3600)
    cache_ttl_info: int = Field(default=3600)

    # OpenAI
    openai_api_key: str = Field(default="")
    openai_model: str = Field(default="gpt-4o-mini")
    openai_vision_model: str = Field(default="gpt-4o")
    openai_whisper_model: str = Field(default="whisper-1")

    # Chatwoot
    chatwoot_base_url: str = Field(default="")
    chatwoot_api_token: str = Field(default="")
    chatwoot_account_id: int = Field(default=1)
    chatwoot_inbox_id: int = Field(default=1)
    chatwoot_webhook_secret: Optional[str] = Field(default=None)
    chatwoot_webhook_token: Optional[str] = Field(default=None)
    chatwoot_internal_url: Optional[str] = Field(default=None)

    # Google Calendar
    google_credentials_path: str = Field(default="/app/credentials/google_service_account.json")
    google_credentials_base64: str = Field(default="")
    google_calendar_id: str = Field(default="")
    calendar_timezone: str = Field(default="America/Mexico_City")

    # Google Drive
    google_drive_folder_id: str = Field(default="")
    backup_retention_days: int = Field(default=30)  # Drive backup rotation

    # Rate Limiting
    rate_limit_max_messages: int = Field(default=30)
    rate_limit_window_seconds: int = Field(default=3600)

    # Message grouping
    message_group_delay: int = Field(default=3)

    # Scheduled Jobs
    owner_phone_number: str = Field(default="")
    weekly_report_day: int = Field(default=0)  # Monday
    weekly_report_hour: int = Field(default=9)
    weekly_report_minute: int = Field(default=0)
    daily_reminder_hour: int = Field(default=18)
    daily_reminder_minute: int = Field(default=0)
    daily_backup_hour: int = Field(default=3)
    daily_backup_minute: int = Field(default=0)
    calendar_sync_interval_minutes: int = Field(default=15)
    auto_resume_hours: int = Field(default=24)  # Auto-resume paused conversations after N hours
    auto_resume_interval_minutes: int = Field(default=60)  # How often to check for stale paused convos

    # Billing
    billing_check_hour: int = Field(default=9)
    billing_check_minute: int = Field(default=0)
    billing_grace_period_days: int = Field(default=3)
    billing_warning_days: str = Field(default="7,3,1")

    # Salon / Business identity
    salon_name: str = Field(default="AgencyBot")
    salon_address: str = Field(default="")
    salon_phone: str = Field(default="")
    salon_hours: str = Field(default="Lunes a Sábado: 9:00 AM - 8:00 PM")
    business_type: str = Field(default="agencia de consultoría en IA")
    currency_symbol: str = Field(default="$")
    whisper_language: str = Field(default="es")

    # Agent behavior
    agent_timeout_seconds: int = Field(default=120)
    agent_temperature: float = Field(default=0.3)
    agent_max_iterations: int = Field(default=10)
    agent_history_limit: int = Field(default=10)
    conversation_context_limit: int = Field(default=20)
    conversation_context_ttl: int = Field(default=3600)

    # Business hours defaults (for availability checks)
    default_business_start_hour: int = Field(default=9)
    default_business_end_hour: int = Field(default=20)
    default_slot_interval: int = Field(default=30)

    # Customizable messages (empty = use built-in default)
    bot_paused_message: str = Field(default="")
    handoff_message: str = Field(default="")
    rate_limit_message: str = Field(default="")
    agent_timeout_message: str = Field(default="")
    agent_error_message: str = Field(default="")

    # System prompt override (empty = use built-in template)
    system_prompt_override: str = Field(default="")
    vision_prompt_override: str = Field(default="")

    # Seed data
    seed_data_enabled: bool = Field(default=True)

    # Redis key prefix (for multi-instance on shared Redis)
    redis_key_prefix: str = Field(default="agencybot")

    # Security - no insecure defaults
    secret_key: str = Field(default="")
    allowed_origins: str = Field(default="")

    # Booking constraints
    max_booking_days_ahead: int = Field(default=90)
    max_attachment_size_bytes: int = Field(default=10_485_760)  # 10 MB
    max_active_appointments_per_user: int = Field(default=3)  # 0 = unlimited

    # Rate limit notifications
    rate_limit_notify_owner: bool = Field(default=True)

    # Human handoff
    handoff_chatwoot_status: str = Field(default="pending")
    handoff_label: str = Field(default="atencion-humana")
    paused_reply_cooldown_seconds: int = Field(default=300)  # 5 min

    # Admin panel
    admin_username: str = Field(default="admin")
    admin_password: str = Field(default="")  # Set to auto-create admin user on startup

    # Telegram error notifications (optional)
    telegram_bot_token: str = Field(default="")
    telegram_chat_id: str = Field(default="")
    telegram_alert_cooldown_seconds: int = Field(default=300)  # 5 min dedup window

    @property
    def telegram_notifications_enabled(self) -> bool:
        return bool(self.telegram_bot_token and self.telegram_chat_id)

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"

    @model_validator(mode="after")
    def validate_production_settings(self) -> "Settings":
        """Validate that critical settings are configured in production."""
        if self.app_env != "production":
            # In development, provide sensible defaults for missing values
            if not self.database_url:
                self.database_url = "postgresql+asyncpg://agencybot_user:password@localhost:5432/agencybot"
            if not self.secret_key:
                import secrets as _s
                self.secret_key = _s.token_hex(32)
            return self

        errors = []
        if not self.database_url:
            errors.append("DATABASE_URL")
        if not self.secret_key:
            errors.append("SECRET_KEY")
        elif len(self.secret_key) < 32:
            errors.append("SECRET_KEY must be at least 32 characters in production")
        if not self.openai_api_key:
            errors.append("OPENAI_API_KEY")
        if not self.chatwoot_base_url:
            errors.append("CHATWOOT_BASE_URL")
        if not self.chatwoot_api_token:
            errors.append("CHATWOOT_API_TOKEN")
        if not self.chatwoot_webhook_secret and not self.chatwoot_webhook_token:
            errors.append("CHATWOOT_WEBHOOK_SECRET or CHATWOOT_WEBHOOK_TOKEN (at least one required for webhook authentication)")
        if not self.google_calendar_id:
            errors.append("GOOGLE_CALENDAR_ID")
        if "@" not in self.redis_url or self.redis_url.startswith("redis://:@"):
            errors.append("REDIS_URL must include a password in production (redis://:PASSWORD@host:port/db)")

        if self.allowed_origins:
            origins = [o.strip() for o in self.allowed_origins.split(",") if o.strip()]
            if "*" in origins:
                errors.append("ALLOWED_ORIGINS must not contain '*' in production — specify explicit origins")

        if self.admin_password:
            import re as _re
            if (
                len(self.admin_password) < 12
                or not _re.search(r"[A-Z]", self.admin_password)
                or not _re.search(r"[a-z]", self.admin_password)
                or not _re.search(r"\d", self.admin_password)
                or not _re.search(r"[^A-Za-z0-9]", self.admin_password)
            ):
                errors.append(
                    "ADMIN_PASSWORD must be at least 12 chars with uppercase, lowercase, digit, and special character"
                )

        if errors:
            msg = f"Missing required environment variables for production: {', '.join(errors)}"
            logger.critical("Missing required environment variables for production", missing=errors)
            raise ValueError(msg)

        return self


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


settings = get_settings()


def get_google_credentials(scopes: list[str]):
    """Get Google service account credentials from base64 env var or file path."""
    import structlog
    from google.oauth2 import service_account

    logger = structlog.get_logger(__name__)

    if settings.google_credentials_base64:
        b64_str = settings.google_credentials_base64.strip()
        # Support URL-safe base64 (uses - and _ instead of + and /)
        raw = base64.urlsafe_b64decode(b64_str + "==")  # pad to be safe
        info = json.loads(raw)
        creds = service_account.Credentials.from_service_account_info(info, scopes=scopes)
        logger.info(
            "Google credentials loaded from base64",
            service_account=creds.service_account_email,
        )
        return creds
    return service_account.Credentials.from_service_account_file(
        settings.google_credentials_path, scopes=scopes
    )
