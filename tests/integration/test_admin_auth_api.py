"""Integration tests for admin authentication API."""

import pytest
from app.models.models import AdminUser, RolAdmin
from app.services.admin_auth_service import hash_password, create_access_token, create_refresh_token


class TestLogin:
    """POST /api/admin/auth/login"""

    async def test_login_success(self, app_client, admin_user):
        resp = await app_client.post("/api/admin/auth/login", json={
            "username": "testadmin",
            "password": "testpass123",  # pragma: allowlist secret
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"] == "bearer"

    async def test_login_wrong_password(self, app_client, admin_user):
        resp = await app_client.post("/api/admin/auth/login", json={
            "username": "testadmin",
            "password": "wrongpass",  # pragma: allowlist secret
        })
        assert resp.status_code == 401

    async def test_login_unknown_user(self, app_client):
        resp = await app_client.post("/api/admin/auth/login", json={
            "username": "nonexistent",
            "password": "whatever",  # pragma: allowlist secret
        })
        assert resp.status_code == 401

    async def test_login_inactive_user(self, app_client, db_session, test_tenant):
        user = AdminUser(
            username="inactive",
            password_hash=hash_password("pass123"),  # pragma: allowlist secret
            rol=RolAdmin.ADMIN,
            activo=False,
            tenant_id=test_tenant.id,
        )
        db_session.add(user)
        await db_session.commit()

        resp = await app_client.post("/api/admin/auth/login", json={
            "username": "inactive",
            "password": "pass123",
        })
        assert resp.status_code == 401
        assert resp.json()["detail"] == "Credenciales incorrectas"


class TestRefreshToken:
    """POST /api/admin/auth/refresh"""

    async def test_refresh_success(self, app_client, admin_user):
        refresh = create_refresh_token(admin_user.username)
        resp = await app_client.post("/api/admin/auth/refresh", json={
            "refresh_token": refresh,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data
        assert "refresh_token" in data

    async def test_refresh_with_access_token_fails(self, app_client, admin_user):
        access = create_access_token(admin_user.username)
        resp = await app_client.post("/api/admin/auth/refresh", json={
            "refresh_token": access,
        })
        assert resp.status_code == 401

    async def test_refresh_invalid_token(self, app_client):
        resp = await app_client.post("/api/admin/auth/refresh", json={
            "refresh_token": "garbage",
        })
        assert resp.status_code == 401


class TestMe:
    """GET /api/admin/auth/me"""

    async def test_get_me(self, admin_client, admin_user):
        resp = await admin_client.get("/api/admin/auth/me")
        assert resp.status_code == 200
        data = resp.json()
        assert data["username"] == "testadmin"
        assert data["rol"] == "admin"

    async def test_get_me_no_auth(self, app_client):
        resp = await app_client.get("/api/admin/auth/me")
        assert resp.status_code == 401


class TestChangePassword:
    """POST /api/admin/auth/change-password"""

    async def test_change_password_success(self, admin_client, admin_user):
        resp = await admin_client.post("/api/admin/auth/change-password", json={
            "current_password": "testpass123",  # pragma: allowlist secret
            "new_password": "Newpass123",  # pragma: allowlist secret
        })
        assert resp.status_code == 200

    async def test_change_password_wrong_current(self, admin_client, admin_user):
        resp = await admin_client.post("/api/admin/auth/change-password", json={
            "current_password": "wrongcurrent",  # pragma: allowlist secret
            "new_password": "Newpass123",  # pragma: allowlist secret
        })
        assert resp.status_code == 400

    async def test_change_password_too_short(self, admin_client, admin_user):
        resp = await admin_client.post("/api/admin/auth/change-password", json={
            "current_password": "testpass123",  # pragma: allowlist secret
            "new_password": "short",  # pragma: allowlist secret
        })
        assert resp.status_code == 422  # Pydantic validation: min_length=8

    async def test_change_password_invalidates_old_tokens(self, app_client, admin_user):
        """After changing password, the old token should be revoked."""
        token = create_access_token(admin_user.username)
        client_headers = {"Authorization": f"Bearer {token}"}

        # Change password with old token
        resp = await app_client.post("/api/admin/auth/change-password", json={
            "current_password": "testpass123",  # pragma: allowlist secret
            "new_password": "Brandnewpass1",  # pragma: allowlist secret
        }, headers=client_headers)
        assert resp.status_code == 200

        # Old token should now be revoked
        resp2 = await app_client.get("/api/admin/auth/me", headers=client_headers)
        assert resp2.status_code == 401


class TestLogout:
    """POST /api/admin/auth/logout"""

    async def test_logout_revokes_access_token(self, app_client, admin_user):
        """After logout, the access token should no longer work."""
        token = create_access_token(admin_user.username)
        headers = {"Authorization": f"Bearer {token}"}

        resp = await app_client.post("/api/admin/auth/logout", json={},
                                      headers=headers)
        assert resp.status_code == 200
        assert resp.json()["detail"] == "Sesion cerrada"

        # Token should be revoked
        resp2 = await app_client.get("/api/admin/auth/me", headers=headers)
        assert resp2.status_code == 401

    async def test_logout_revokes_refresh_token(self, app_client, admin_user):
        """Logout with refresh_token should revoke it too."""
        access = create_access_token(admin_user.username)
        refresh = create_refresh_token(admin_user.username)
        headers = {"Authorization": f"Bearer {access}"}

        resp = await app_client.post("/api/admin/auth/logout",
                                      json={"refresh_token": refresh},
                                      headers=headers)
        assert resp.status_code == 200

        # Refresh token should be revoked
        resp2 = await app_client.post("/api/admin/auth/refresh",
                                       json={"refresh_token": refresh})
        assert resp2.status_code == 401

    async def test_logout_no_auth_rejected(self, app_client):
        resp = await app_client.post("/api/admin/auth/logout", json={})
        assert resp.status_code == 401


class TestRefreshTokenRotation:
    """Refresh token rotation: old token invalidated after use."""

    async def test_old_refresh_token_rejected_after_rotation(self, app_client, admin_user):
        """After refreshing, the old refresh token should no longer work."""
        old_refresh = create_refresh_token(admin_user.username)

        # First refresh — should succeed
        resp = await app_client.post("/api/admin/auth/refresh",
                                      json={"refresh_token": old_refresh})
        assert resp.status_code == 200
        new_tokens = resp.json()
        assert "access_token" in new_tokens
        assert "refresh_token" in new_tokens

        # Old refresh token — should be rejected (blacklisted)
        resp2 = await app_client.post("/api/admin/auth/refresh",
                                       json={"refresh_token": old_refresh})
        assert resp2.status_code == 401

    async def test_new_refresh_token_works_after_rotation(self, app_client, admin_user):
        """The newly issued refresh token should work."""
        old_refresh = create_refresh_token(admin_user.username)

        resp = await app_client.post("/api/admin/auth/refresh",
                                      json={"refresh_token": old_refresh})
        assert resp.status_code == 200
        new_refresh = resp.json()["refresh_token"]

        # New token should work
        resp2 = await app_client.post("/api/admin/auth/refresh",
                                       json={"refresh_token": new_refresh})
        assert resp2.status_code == 200
