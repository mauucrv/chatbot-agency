"""
Redis cache service for caching salon data.
"""

import base64
import hashlib
import json
from datetime import datetime, timezone

import structlog
from typing import Any, List, Optional

import asyncio

import redis.asyncio as redis
from cryptography.fernet import Fernet, InvalidToken

from app.config import settings

logger = structlog.get_logger(__name__)


class RedisCache:
    """Service for caching data in Redis."""

    def __init__(self):
        """Initialize the Redis cache."""
        self._client: Optional[redis.Redis] = None
        self._init_lock = asyncio.Lock()
        # Configurable key prefix for multi-instance isolation
        self._prefix = settings.redis_key_prefix

    def _tkey(self, tenant_id: int, *parts: str) -> str:
        """Build a tenant-scoped Redis key: {prefix}:t:{tenant_id}:{parts}."""
        return f"{self._prefix}:t:{tenant_id}:{':'.join(parts)}"

    def _gkey(self, *parts: str) -> str:
        """Build a global (non-tenant) Redis key: {prefix}:{parts}."""
        return f"{self._prefix}:{':'.join(parts)}"

    def _get_fernet(self) -> Fernet:
        """Derive a Fernet key from SECRET_KEY using PBKDF2 and return a Fernet instance."""
        if not hasattr(self, "_fernet"):
            # Derive a 32-byte key from SECRET_KEY using PBKDF2
            dk = hashlib.pbkdf2_hmac(
                "sha256",
                settings.secret_key.encode(),
                b"agencybot-redis-conversation-context",  # static salt
                iterations=100_000,
            )
            fernet_key = base64.urlsafe_b64encode(dk)
            self._fernet = Fernet(fernet_key)
        return self._fernet

    def _encrypt(self, data: str) -> str:
        """Encrypt a string and return base64-encoded ciphertext."""
        return self._get_fernet().encrypt(data.encode()).decode()

    def _decrypt(self, token: str) -> str:
        """Decrypt base64-encoded ciphertext and return the original string."""
        return self._get_fernet().decrypt(token.encode()).decode()

    async def get_client(self) -> redis.Redis:
        """Get or create the Redis client with automatic reconnection."""
        if self._client is not None:
            return self._client
        async with self._init_lock:
            # Double-check after acquiring lock
            if self._client is None:
                self._client = redis.from_url(
                    settings.redis_url,
                    encoding="utf-8",
                    decode_responses=True,
                    socket_timeout=5,
                    socket_connect_timeout=5,
                    retry_on_timeout=True,
                    health_check_interval=30,
                )
                logger.info("Redis client initialized")
        return self._client

    async def close(self) -> None:
        """Close the Redis connection."""
        if self._client:
            await self._client.close()
            self._client = None
            logger.info("Redis connection closed")

    async def _reconnect(self) -> None:
        """Force reconnection on next call."""
        if self._client:
            try:
                await self._client.close()
            except Exception:
                pass
            self._client = None

    async def ping(self) -> bool:
        """Check if Redis is available."""
        try:
            client = await self.get_client()
            await client.ping()
            return True
        except Exception as e:
            logger.error("Redis ping failed", error=str(e))
            await self._reconnect()
            return False

    # ============================================================
    # Generic cache operations
    # ============================================================

    async def get(self, key: str) -> Optional[Any]:
        """Get a value from cache."""
        try:
            client = await self.get_client()
            value = await client.get(key)
            if value:
                return json.loads(value)
            return None
        except Exception as e:
            logger.error("Error getting from cache", key=key, error=str(e))
            await self._reconnect()
            return None

    async def set(
        self, key: str, value: Any, ttl: Optional[int] = None
    ) -> bool:
        """Set a value in cache."""
        try:
            client = await self.get_client()
            serialized = json.dumps(value, default=str)
            if ttl:
                await client.setex(key, ttl, serialized)
            else:
                await client.set(key, serialized)
            return True
        except Exception as e:
            logger.error("Error setting cache", key=key, error=str(e))
            await self._reconnect()
            return False

    async def delete(self, key: str) -> bool:
        """Delete a value from cache."""
        try:
            client = await self.get_client()
            await client.delete(key)
            return True
        except Exception as e:
            logger.error("Error deleting from cache", key=key, error=str(e))
            await self._reconnect()
            return False

    async def exists(self, key: str) -> bool:
        """Check if a key exists in cache."""
        try:
            client = await self.get_client()
            return await client.exists(key) > 0
        except Exception as e:
            logger.error("Error checking cache existence", key=key, error=str(e))
            await self._reconnect()
            return False

    # ============================================================
    # Services cache (tenant-scoped)
    # ============================================================

    async def get_services(self, tenant_id: int) -> Optional[List[dict]]:
        """Get cached services for a tenant."""
        return await self.get(self._tkey(tenant_id, "services"))

    async def set_services(self, tenant_id: int, services: List[dict]) -> bool:
        """Cache services for a tenant."""
        return await self.set(
            self._tkey(tenant_id, "services"), services, settings.cache_ttl_services
        )

    async def invalidate_services(self, tenant_id: int) -> bool:
        """Invalidate services cache for a tenant."""
        return await self.delete(self._tkey(tenant_id, "services"))

    # ============================================================
    # Stylists cache (tenant-scoped)
    # ============================================================

    async def get_stylists(self, tenant_id: int) -> Optional[List[dict]]:
        """Get cached stylists for a tenant."""
        return await self.get(self._tkey(tenant_id, "stylists"))

    async def set_stylists(self, tenant_id: int, stylists: List[dict]) -> bool:
        """Cache stylists for a tenant."""
        return await self.set(
            self._tkey(tenant_id, "stylists"), stylists, settings.cache_ttl_stylists
        )

    async def invalidate_stylists(self, tenant_id: int) -> bool:
        """Invalidate stylists cache for a tenant."""
        return await self.delete(self._tkey(tenant_id, "stylists"))

    # ============================================================
    # Salon info cache (tenant-scoped)
    # ============================================================

    async def get_info(self, tenant_id: int) -> Optional[dict]:
        """Get cached salon info for a tenant."""
        return await self.get(self._tkey(tenant_id, "info"))

    async def set_info(self, tenant_id: int, info: dict) -> bool:
        """Cache salon info for a tenant."""
        return await self.set(self._tkey(tenant_id, "info"), info, settings.cache_ttl_info)

    async def invalidate_info(self, tenant_id: int) -> bool:
        """Invalidate salon info cache for a tenant."""
        return await self.delete(self._tkey(tenant_id, "info"))

    # ============================================================
    # Keywords cache (tenant-scoped)
    # ============================================================

    async def get_keywords(self, tenant_id: int) -> Optional[List[str]]:
        """Get cached human keywords for a tenant."""
        return await self.get(self._tkey(tenant_id, "keywords_humano"))

    async def set_keywords(self, tenant_id: int, keywords: List[str]) -> bool:
        """Cache human keywords for a tenant."""
        return await self.set(self._tkey(tenant_id, "keywords_humano"), keywords, settings.cache_ttl_info)

    async def invalidate_keywords(self, tenant_id: int) -> bool:
        """Invalidate keywords cache for a tenant."""
        return await self.delete(self._tkey(tenant_id, "keywords_humano"))

    # ============================================================
    # Rate limiting (fail-closed: reject when Redis is down)
    # ============================================================

    async def check_rate_limit(
        self, tenant_id: int, phone_number: str, max_messages: int, window_seconds: int
    ) -> tuple[bool, int]:
        """
        Check if a phone number has exceeded the rate limit (per-tenant).
        Fail-closed: if Redis is unavailable, messages are rejected.

        Returns:
            Tuple of (is_allowed, current_count)
        """
        try:
            client = await self.get_client()
            key = self._tkey(tenant_id, "rate_limit", phone_number)

            # Get current count
            count = await client.get(key)
            current_count = int(count) if count else 0

            if current_count >= max_messages:
                logger.warning(
                    "Rate limit exceeded",
                    tenant_id=tenant_id,
                    phone=phone_number[-4:],
                    count=current_count,
                )
                return False, current_count

            # Increment count
            pipe = client.pipeline()
            pipe.incr(key)
            pipe.expire(key, window_seconds)
            await pipe.execute()

            return True, current_count + 1

        except Exception as e:
            logger.error("Redis unavailable for rate limiting - rejecting message (fail-closed)", error=str(e))
            await self._reconnect()
            return False, -1

    async def should_send_paused_reply(
        self, tenant_id: int, conversation_id: int, cooldown_seconds: int
    ) -> bool:
        """
        Check if a paused-conversation reply should be sent (per-tenant).
        Throttles to 1 reply per cooldown window per conversation.
        """
        try:
            client = await self.get_client()
            key = self._tkey(tenant_id, "paused_reply_cooldown", str(conversation_id))
            result = await client.set(key, "1", ex=cooldown_seconds, nx=True)
            return result is True
        except Exception as e:
            logger.error("Error checking paused reply cooldown", error=str(e))
            await self._reconnect()
            return False  # Fail-safe: don't spam customer

    async def clear_paused_reply_cooldown(self, tenant_id: int, conversation_id: int) -> bool:
        """Clear paused reply cooldown when bot reactivates."""
        try:
            client = await self.get_client()
            key = self._tkey(tenant_id, "paused_reply_cooldown", str(conversation_id))
            await client.delete(key)
            return True
        except Exception as e:
            logger.error("Error clearing paused reply cooldown", error=str(e))
            await self._reconnect()
            return False

    async def mark_rate_limit_owner_notified(
        self, tenant_id: int, phone_number: str, window_seconds: int
    ) -> bool:
        """
        Check if the owner should be notified about a rate-limited phone (per-tenant).
        Uses SET NX so only the first call per window returns True.
        """
        try:
            client = await self.get_client()
            key = self._tkey(tenant_id, "rate_limit_owner_notified", phone_number)
            result = await client.set(key, "1", ex=window_seconds, nx=True)
            return result is True
        except Exception as e:
            logger.error("Error checking rate limit owner notification", error=str(e))
            await self._reconnect()
            return False  # Fail-safe: don't spam owner

    async def get_rate_limit_remaining(
        self, tenant_id: int, phone_number: str, max_messages: int
    ) -> int:
        """Get remaining messages for a phone number (per-tenant)."""
        try:
            client = await self.get_client()
            key = self._tkey(tenant_id, "rate_limit", phone_number)
            count = await client.get(key)
            current_count = int(count) if count else 0
            return max(0, max_messages - current_count)
        except Exception as e:
            logger.error("Error getting rate limit remaining", error=str(e))
            await self._reconnect()
            return 0

    # ============================================================
    # Booking lock (distributed lock for race condition prevention)
    # ============================================================

    async def acquire_booking_lock(
        self, tenant_id: int, slot_key: str, ttl: int = 30
    ) -> bool:
        """
        Acquire a distributed lock for a booking time slot (per-tenant).
        Prevents double-booking via TOCTOU race condition.
        """
        try:
            client = await self.get_client()
            key = self._tkey(tenant_id, "booking_lock", slot_key)
            result = await client.set(key, "1", ex=ttl, nx=True)
            return result is True
        except Exception as e:
            logger.error("Error acquiring booking lock", slot_key=slot_key, error=str(e))
            await self._reconnect()
            return False

    async def release_booking_lock(self, tenant_id: int, slot_key: str) -> bool:
        """Release a booking lock (per-tenant)."""
        try:
            client = await self.get_client()
            key = self._tkey(tenant_id, "booking_lock", slot_key)
            await client.delete(key)
            return True
        except Exception as e:
            logger.error("Error releasing booking lock", slot_key=slot_key, error=str(e))
            await self._reconnect()
            return False

    # ============================================================
    # Message grouping
    # ============================================================

    async def add_pending_message(
        self, tenant_id: int, conversation_id: int, message: dict, ttl: int = 60
    ) -> List[dict]:
        """Add a message to the pending messages list for a conversation (per-tenant)."""
        try:
            client = await self.get_client()
            key = self._tkey(tenant_id, "pending_messages", str(conversation_id))

            # Get existing messages
            existing = await client.get(key)
            messages = json.loads(existing) if existing else []

            # Add new message
            messages.append(message)

            # Save with TTL
            await client.setex(key, ttl, json.dumps(messages, default=str))

            return messages

        except Exception as e:
            logger.error("Error adding pending message", error=str(e))
            await self._reconnect()
            return [message]

    async def get_pending_messages(self, tenant_id: int, conversation_id: int) -> List[dict]:
        """Get pending messages for a conversation (per-tenant)."""
        try:
            client = await self.get_client()
            key = self._tkey(tenant_id, "pending_messages", str(conversation_id))
            value = await client.get(key)
            return json.loads(value) if value else []
        except Exception as e:
            logger.error("Error getting pending messages", error=str(e))
            await self._reconnect()
            return []

    async def clear_pending_messages(self, tenant_id: int, conversation_id: int) -> bool:
        """Clear pending messages for a conversation (per-tenant)."""
        try:
            client = await self.get_client()
            key = self._tkey(tenant_id, "pending_messages", str(conversation_id))
            await client.delete(key)
            return True
        except Exception as e:
            logger.error("Error clearing pending messages", error=str(e))
            await self._reconnect()
            return False

    async def set_processing_lock(
        self, tenant_id: int, conversation_id: int, ttl: int = 30
    ) -> bool:
        """Set a processing lock for a conversation (per-tenant, NX = only if not exists)."""
        try:
            client = await self.get_client()
            key = self._tkey(tenant_id, "processing_lock", str(conversation_id))
            result = await client.set(key, "1", ex=ttl, nx=True)
            return result is True
        except Exception as e:
            logger.error("Error setting processing lock", error=str(e))
            await self._reconnect()
            return False

    async def release_processing_lock(self, tenant_id: int, conversation_id: int) -> bool:
        """Release a processing lock for a conversation (per-tenant)."""
        try:
            client = await self.get_client()
            key = self._tkey(tenant_id, "processing_lock", str(conversation_id))
            await client.delete(key)
            return True
        except Exception as e:
            logger.error("Error releasing processing lock", error=str(e))
            await self._reconnect()
            return False

    # ============================================================
    # Conversation context
    # ============================================================

    async def get_conversation_context(
        self, tenant_id: int, conversation_id: int
    ) -> Optional[List[dict]]:
        """Get cached conversation context (decrypted from Redis, per-tenant)."""
        try:
            client = await self.get_client()
            key = self._tkey(tenant_id, "conversation_context", str(conversation_id))
            value = await client.get(key)
            if not value:
                return None
            decrypted = self._decrypt(value)
            return json.loads(decrypted)
        except InvalidToken:
            logger.warning(
                "Failed to decrypt conversation context — key may have changed, clearing stale entry",
                conversation_id=conversation_id,
            )
            await self.clear_conversation_context(tenant_id, conversation_id)
            return None
        except Exception as e:
            logger.error("Error getting conversation context", conversation_id=conversation_id, error=str(e))
            await self._reconnect()
            return None

    async def set_conversation_context(
        self, tenant_id: int, conversation_id: int, context: List[dict], ttl: int = 3600
    ) -> bool:
        """Cache conversation context (encrypted in Redis, per-tenant)."""
        try:
            client = await self.get_client()
            key = self._tkey(tenant_id, "conversation_context", str(conversation_id))
            serialized = json.dumps(context, default=str)
            encrypted = self._encrypt(serialized)
            await client.setex(key, ttl, encrypted)
            return True
        except Exception as e:
            logger.error("Error setting conversation context", conversation_id=conversation_id, error=str(e))
            await self._reconnect()
            return False

    async def clear_conversation_context(self, tenant_id: int, conversation_id: int) -> bool:
        """Clear cached conversation context (per-tenant)."""
        key = self._tkey(tenant_id, "conversation_context", str(conversation_id))
        return await self.delete(key)

    # ============================================================
    # Admin — login rate limiting
    # ============================================================

    async def check_login_rate_limit(
        self, identifier: str, max_attempts: int = 5, window_seconds: int = 900
    ) -> tuple[bool, int]:
        """
        Check login rate limit. Returns (allowed, current_count).
        Fail-closed: if Redis is down, reject the attempt.
        """
        key = f"{self._prefix}:admin_login_attempts:{identifier}"
        try:
            client = await self.get_client()
            count = await client.incr(key)
            if count == 1:
                await client.expire(key, window_seconds)
            return (count <= max_attempts, count)
        except Exception:
            logger.error("Redis unavailable during login rate limiting — rejecting attempt")
            return (False, -1)

    async def clear_login_attempts(self, identifier: str) -> None:
        """Clear login attempts after successful login."""
        key = f"{self._prefix}:admin_login_attempts:{identifier}"
        await self.delete(key)

    # ============================================================
    # Token blacklist (JWT revocation)
    # ============================================================

    async def blacklist_token(self, jti: str, ttl_seconds: int) -> bool:
        """Add a token JTI to the blacklist. TTL auto-expires when token would have expired."""
        try:
            client = await self.get_client()
            key = f"{self._prefix}:token_blacklist:{jti}"
            await client.set(key, "1", ex=max(ttl_seconds, 1))
            return True
        except Exception as e:
            logger.error("redis_blacklist_token_error", error=str(e))
            return False

    async def is_token_blacklisted(self, jti: str) -> bool:
        """Check if token JTI is blacklisted. Fail-closed on Redis error (reject request)."""
        try:
            client = await self.get_client()
            key = f"{self._prefix}:token_blacklist:{jti}"
            result = await client.get(key)
            return result is not None
        except Exception:
            return True  # fail-closed: if Redis down, treat token as blacklisted

    async def invalidate_user_tokens(self, username: str) -> bool:
        """Store timestamp marking all tokens issued before now as invalid for this user."""
        try:
            client = await self.get_client()
            key = f"{self._prefix}:user_tokens_invalidated:{username}"
            import time
            await client.set(key, str(time.time()), ex=7 * 86400)  # 7 days = max refresh token lifetime
            return True
        except Exception as e:
            logger.error("redis_invalidate_user_tokens_error", error=str(e))
            return False

    async def get_user_tokens_invalidated_at(self, username: str) -> float | None:
        """Get the timestamp after which tokens for this user are invalid.
        Fail-closed: returns current time on Redis error, treating all tokens as invalidated."""
        try:
            client = await self.get_client()
            key = f"{self._prefix}:user_tokens_invalidated:{username}"
            result = await client.get(key)
            return float(result) if result else None
        except Exception:
            return datetime.now(timezone.utc).timestamp()  # fail-closed: treat all tokens as invalidated

    async def check_refresh_rate_limit(
        self, identifier: str, max_attempts: int = 20, window_seconds: int = 900
    ) -> tuple[bool, int]:
        """Rate limit refresh token requests. Fail-closed: reject if Redis is down."""
        key = f"{self._prefix}:admin_refresh_attempts:{identifier}"
        try:
            client = await self.get_client()
            current = await client.incr(key)
            if current == 1:
                await client.expire(key, window_seconds)
            if current > max_attempts:
                return False, current
            return True, current
        except Exception:
            logger.error("Redis unavailable during refresh rate limiting — rejecting attempt")
            return False, -1

    # ============================================================
    # Admin — dashboard / stats cache
    # ============================================================

    # ============================================================
    # Usage metrics helpers
    # ============================================================

    async def track_unique_user(self, tenant_id: int, phone_number: str) -> bool:
        """Add a phone to today's unique-user HyperLogLog. Returns True if new."""
        try:
            client = await self.get_client()
            today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            key = self._tkey(tenant_id, "unique_users", today)
            added = await client.pfadd(key, phone_number)
            # Expire at end of next day (safety margin)
            await client.expire(key, 172800)  # 48h
            return bool(added)
        except Exception as e:
            logger.error("Error tracking unique user", error=str(e))
            await self._reconnect()
            return False

    async def get_unique_user_count(self, tenant_id: int, date_str: str) -> int:
        """Get unique user count for a specific date."""
        try:
            client = await self.get_client()
            key = self._tkey(tenant_id, "unique_users", date_str)
            return await client.pfcount(key)
        except Exception as e:
            logger.error("Error getting unique user count", error=str(e))
            await self._reconnect()
            return 0

    async def get_admin_cache(self, tenant_id: int, cache_key: str) -> Any:
        """Get cached admin data (dashboard, stats, etc.) per-tenant."""
        key = self._tkey(tenant_id, "admin_cache", cache_key)
        return await self.get(key)

    async def set_admin_cache(self, tenant_id: int, cache_key: str, value: Any, ttl: int = 60) -> bool:
        """Cache admin data with short TTL per-tenant."""
        key = self._tkey(tenant_id, "admin_cache", cache_key)
        return await self.set(key, value, ttl)

    async def invalidate_admin_cache_pattern(self, tenant_id: int, pattern: str) -> bool:
        """Invalidate admin cache keys matching a pattern for a tenant."""
        try:
            client = await self.get_client()
            full_pattern = self._tkey(tenant_id, "admin_cache", f"{pattern}*")
            cursor = 0
            while True:
                cursor, keys = await client.scan(cursor, match=full_pattern, count=100)
                if keys:
                    await client.delete(*keys)
                if cursor == 0:
                    break
            return True
        except Exception as e:
            logger.error("Error invalidating admin cache pattern", pattern=pattern, error=str(e))
            await self._reconnect()
            return False

    async def invalidate_fichas(self, tenant_id: int) -> bool:
        """Invalidate client profiles cache."""
        return await self.invalidate_admin_cache_pattern(tenant_id, "fichas")

    async def invalidate_inventario(self, tenant_id: int) -> bool:
        """Invalidate inventory cache."""
        return await self.invalidate_admin_cache_pattern(tenant_id, "inventario")

    async def invalidate_ventas(self, tenant_id: int) -> bool:
        """Invalidate sales cache."""
        return await self.invalidate_admin_cache_pattern(tenant_id, "ventas")

    async def invalidate_informes(self, tenant_id: int) -> bool:
        """Invalidate all report caches."""
        return await self.invalidate_admin_cache_pattern(tenant_id, "informes")


# Singleton instance
redis_cache = RedisCache()
