"""Tests for webhook authentication (verify_webhook_auth)."""

import hashlib
import hmac
import pytest
from unittest.mock import patch


def _make_hmac(payload: bytes, secret: str) -> str:
    return hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()


class TestTokenAuth:
    """URL token-based authentication."""

    def test_correct_token(self):
        from app.api.webhooks import verify_webhook_auth
        with patch("app.api.webhooks.settings") as s:
            s.chatwoot_webhook_token = "my-token"
            s.chatwoot_webhook_secret = None
            assert verify_webhook_auth(b"payload", token="my-token") is True

    def test_wrong_token(self):
        from app.api.webhooks import verify_webhook_auth
        with patch("app.api.webhooks.settings") as s:
            s.chatwoot_webhook_token = "my-token"
            s.chatwoot_webhook_secret = None
            assert verify_webhook_auth(b"payload", token="wrong") is False

    def test_missing_token(self):
        from app.api.webhooks import verify_webhook_auth
        with patch("app.api.webhooks.settings") as s:
            s.chatwoot_webhook_token = "my-token"
            s.chatwoot_webhook_secret = None
            assert verify_webhook_auth(b"payload", token=None) is False


class TestHmacAuth:
    """HMAC signature-based authentication."""

    def test_valid_signature(self):
        from app.api.webhooks import verify_webhook_auth
        secret = "my-secret"  # pragma: allowlist secret
        payload = b'{"event": "message_created"}'
        sig = _make_hmac(payload, secret)
        with patch("app.api.webhooks.settings") as s:
            s.chatwoot_webhook_token = None
            s.chatwoot_webhook_secret = secret
            assert verify_webhook_auth(payload, signature=sig) is True

    def test_invalid_signature(self):
        from app.api.webhooks import verify_webhook_auth
        with patch("app.api.webhooks.settings") as s:
            s.chatwoot_webhook_token = None
            s.chatwoot_webhook_secret = "my-secret"
            assert verify_webhook_auth(b"payload", signature="wrong") is False

    def test_missing_signature(self):
        from app.api.webhooks import verify_webhook_auth
        with patch("app.api.webhooks.settings") as s:
            s.chatwoot_webhook_token = None
            s.chatwoot_webhook_secret = "my-secret"
            assert verify_webhook_auth(b"payload", signature=None) is False


class TestNoAuthConfigured:
    """Behavior when no auth method is configured."""

    def test_production_rejects(self):
        from app.api.webhooks import verify_webhook_auth
        with patch("app.api.webhooks.settings") as s:
            s.chatwoot_webhook_token = None
            s.chatwoot_webhook_secret = None
            s.is_production = True
            assert verify_webhook_auth(b"payload") is False

    def test_development_allows(self):
        from app.api.webhooks import verify_webhook_auth
        with patch("app.api.webhooks.settings") as s:
            s.chatwoot_webhook_token = None
            s.chatwoot_webhook_secret = None
            s.is_production = False
            assert verify_webhook_auth(b"payload") is True
