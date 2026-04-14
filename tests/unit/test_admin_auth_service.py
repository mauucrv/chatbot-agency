"""Tests for admin authentication service — JWT and password hashing."""

import pytest
from datetime import datetime, timedelta, timezone

from app.services.admin_auth_service import (
    create_access_token,
    create_refresh_token,
    decode_token,
    decode_token_full,
    hash_password,
    verify_password,
    ALGORITHM,
)


class TestPasswordHashing:
    """Password hashing with bcrypt."""

    def test_hash_returns_bcrypt_format(self):
        hashed = hash_password("mypassword")
        assert hashed.startswith("$2b$")

    def test_verify_correct_password(self):
        hashed = hash_password("mypassword")
        assert verify_password("mypassword", hashed) is True

    def test_verify_wrong_password(self):
        hashed = hash_password("mypassword")
        assert verify_password("wrongpassword", hashed) is False

    def test_hash_is_unique_per_call(self):
        h1 = hash_password("same")
        h2 = hash_password("same")
        assert h1 != h2  # Different salts


class TestAccessToken:
    """Access token creation and decoding."""

    def test_create_and_decode(self):
        token = create_access_token("testuser")
        result = decode_token(token, expected_type="access")
        assert result == "testuser"

    def test_has_access_type(self):
        import jwt
        from app.config import settings
        token = create_access_token("testuser")
        payload = jwt.decode(token, settings.secret_key, algorithms=[ALGORITHM])
        assert payload["type"] == "access"
        assert payload["sub"] == "testuser"

    def test_rejects_as_refresh(self):
        token = create_access_token("testuser")
        result = decode_token(token, expected_type="refresh")
        assert result is None


class TestRefreshToken:
    """Refresh token creation and decoding."""

    def test_create_and_decode(self):
        token = create_refresh_token("testuser")
        result = decode_token(token, expected_type="refresh")
        assert result == "testuser"

    def test_has_refresh_type(self):
        import jwt
        from app.config import settings
        token = create_refresh_token("testuser")
        payload = jwt.decode(token, settings.secret_key, algorithms=[ALGORITHM])
        assert payload["type"] == "refresh"

    def test_rejects_as_access(self):
        token = create_refresh_token("testuser")
        result = decode_token(token, expected_type="access")
        assert result is None


class TestDecodeToken:
    """Token decoding edge cases."""

    def test_rejects_expired_token(self):
        import jwt
        from app.config import settings
        payload = {
            "sub": "testuser",
            "exp": datetime.now(timezone.utc) - timedelta(hours=1),
            "type": "access",
        }
        token = jwt.encode(payload, settings.secret_key, algorithm=ALGORITHM)
        assert decode_token(token) is None

    def test_rejects_invalid_token(self):
        assert decode_token("not-a-valid-jwt") is None

    def test_rejects_wrong_key(self):
        import jwt
        payload = {
            "sub": "testuser",
            "exp": datetime.now(timezone.utc) + timedelta(hours=1),
            "type": "access",
        }
        token = jwt.encode(payload, "wrong-secret-key", algorithm=ALGORITHM)
        assert decode_token(token) is None

    def test_rejects_missing_type(self):
        import jwt
        from app.config import settings
        payload = {
            "sub": "testuser",
            "exp": datetime.now(timezone.utc) + timedelta(hours=1),
        }
        token = jwt.encode(payload, settings.secret_key, algorithm=ALGORITHM)
        assert decode_token(token) is None


class TestDecodeTokenFull:
    """decode_token_full returns full payload dict."""

    def test_returns_full_payload(self):
        token = create_access_token("testuser")
        payload = decode_token_full(token)
        assert payload is not None
        assert payload["sub"] == "testuser"
        assert payload["type"] == "access"
        assert "jti" in payload
        assert "iat" in payload
        assert "exp" in payload

    def test_returns_none_for_invalid(self):
        assert decode_token_full("not-a-jwt") is None

    def test_returns_none_for_missing_sub(self):
        import jwt
        from app.config import settings
        token = jwt.encode(
            {"exp": datetime.now(timezone.utc) + timedelta(hours=1), "type": "access"},
            settings.secret_key,
            algorithm=ALGORITHM,
        )
        assert decode_token_full(token) is None


class TestTokenClaims:
    """Verify jti and iat claims are present and unique."""

    def test_access_token_has_jti(self):
        payload = decode_token_full(create_access_token("user1"))
        assert "jti" in payload
        assert len(payload["jti"]) == 36  # UUID format

    def test_refresh_token_has_jti(self):
        payload = decode_token_full(create_refresh_token("user1"))
        assert "jti" in payload

    def test_jti_is_unique_per_token(self):
        p1 = decode_token_full(create_access_token("user1"))
        p2 = decode_token_full(create_access_token("user1"))
        assert p1["jti"] != p2["jti"]

    def test_iat_is_present(self):
        payload = decode_token_full(create_access_token("user1"))
        assert "iat" in payload
        # iat should be close to now (within 5 seconds)
        import time
        assert abs(payload["iat"] - time.time()) < 5
