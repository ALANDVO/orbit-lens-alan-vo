import pytest
from httpx import AsyncClient
from app.main import app
from app.core.auth import (
    create_access_token,
    create_refresh_token,
    verify_refresh_token,
    reset_oidc_cache,
)
from app.models import User, UserRole
from app.core.config import settings


# Ensure test mode
settings.ENVIRONMENT = "test"
settings.DEBUG = True
reset_oidc_cache()


@pytest.mark.asyncio
async def test_login_config():
    """Login endpoint returns OIDC config."""
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.get("/api/v1/auth/login")
        assert response.status_code == 200
        data = response.json()
        assert data["client_id"] == settings.OIDC_CLIENT_ID
        assert data["redirect_uri"] == settings.OIDC_REDIRECT_URI
        assert "openid" in data["scopes"]


@pytest.mark.asyncio
async def test_auth_config():
    """Config endpoint returns auth settings."""
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.get("/api/v1/auth/config")
        assert response.status_code == 200
        data = response.json()
        assert data["issuer"] == settings.OIDC_ISSUER_URL
        assert data["client_id"] == settings.OIDC_CLIENT_ID
        assert "scopes" in data


@pytest.mark.asyncio
async def test_me_unauthorized():
    """Unauthenticated request to /me returns 401."""
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.get("/api/v1/auth/me")
        assert response.status_code == 401


@pytest.mark.asyncio
async def test_me_authenticated(test_user, auth_headers):
    """Authenticated request to /me returns user data."""
    async with AsyncClient(app=app, base_url="http://test", headers=auth_headers) as client:
        response = await client.get("/api/v1/auth/me")
        assert response.status_code == 200
        data = response.json()
        assert data["email"] == "test@example.com"
        assert data["username"] == "testuser"
        assert data["role"] == "analyst"
        assert data["is_active"] is True


@pytest.mark.asyncio
async def test_logout_authenticated(test_user, auth_headers):
    """Authenticated logout returns success."""
    async with AsyncClient(app=app, base_url="http://test", headers=auth_headers) as client:
        response = await client.post("/api/v1/auth/logout")
        assert response.status_code == 200
        assert response.json()["message"] == "Logged out successfully"


@pytest.mark.asyncio
async def test_create_access_token():
    """Access token creation produces valid JWT."""
    token = create_access_token({"sub": "1", "keycloak_id": "test-user-123", "role": "analyst"})
    assert token is not None
    # Verify token can be decoded
    payload = verify_refresh_token(create_refresh_token({"sub": "1", "keycloak_id": "test-user-123"}))
    assert payload["sub"] == "1"
    assert payload["keycloak_id"] == "test-user-123"
    assert payload["type"] == "refresh"


@pytest.mark.asyncio
async def test_verify_refresh_token_valid():
    """Valid refresh token is verified successfully."""
    token = create_refresh_token({"sub": "1", "keycloak_id": "test-user-123"})
    payload = verify_refresh_token(token)
    assert payload["type"] == "refresh"


@pytest.mark.asyncio
async def test_verify_refresh_token_invalid_type():
    """Token with wrong type is rejected."""
    token = create_access_token({"sub": "1", "keycloak_id": "test-user-123", "role": "analyst"})
    from fastapi import HTTPException
    with pytest.raises(HTTPException) as exc_info:
        verify_refresh_token(token)
    assert exc_info.value.status_code == 401


@pytest.mark.asyncio
async def test_token_expired():
    """Expired tokens are rejected."""
    from jose import jwt
    from datetime import datetime, timezone, timedelta

    # Create an expired token manually
    to_encode = {
        "sub": "1",
        "keycloak_id": "test-user-123",
        "role": "analyst",
        "exp": datetime.now(timezone.utc) - timedelta(minutes=1),
        "iat": datetime.now(timezone.utc) - timedelta(minutes=2),
        "type": "access",
    }
    expired_token = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)

    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {expired_token}"},
        )
        assert response.status_code == 401
