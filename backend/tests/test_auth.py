import pytest
from httpx import AsyncClient, ASGITransport
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


async def get_test_client():
    transport = ASGITransport(app=app)
    return AsyncClient(transport=transport, base_url="http://test")


@pytest.mark.asyncio
async def test_login_config():
    """Login endpoint returns OIDC config."""
    async with await get_test_client() as client:
        response = await client.get("/api/v1/auth/login")
        assert response.status_code == 200
        data = response.json()
        assert data["client_id"] == settings.OIDC_CLIENT_ID
        assert data["redirect_uri"] == settings.OIDC_REDIRECT_URI
        assert "openid" in data["scopes"]


@pytest.mark.asyncio
async def test_auth_config():
    """Config endpoint returns auth settings."""
    async with await get_test_client() as client:
        response = await client.get("/api/v1/auth/config")
        assert response.status_code == 200
        data = response.json()
        assert data["client_id"] == settings.OIDC_CLIENT_ID
        assert "scopes" in data


@pytest.mark.asyncio
async def test_me_unauthorized():
    """Unauthenticated request to /me returns 401."""
    async with await get_test_client() as client:
        response = await client.get("/api/v1/auth/me")
        assert response.status_code == 401


@pytest.mark.asyncio
async def test_me_authenticated(test_user, auth_headers, client):
    """Authenticated request to /me returns user data."""
    response = await client.get("/api/v1/auth/me", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == test_user.id
    assert data["email"] == test_user.email
    assert data["role"] == test_user.role.value
    assert data["is_active"] is True


@pytest.mark.asyncio
async def test_logout_authenticated(test_user, auth_headers, client):
    """Authenticated logout returns success."""
    response = await client.post("/api/v1/auth/logout", headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["message"] == "Logged out successfully"


@pytest.mark.asyncio
async def test_create_access_token():
    """Access token creation produces valid JWT."""
    token = create_access_token({"sub": "1", "role": "analyst"})
    # Verify it can be decoded (not using verify_refresh_token since it's an access token)
    from jose import jwt
    payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    assert payload["sub"] == "1"
    assert payload["role"] == "analyst"
    assert payload["type"] == "access"


@pytest.mark.asyncio
async def test_verify_refresh_token_valid():
    """Valid refresh token is verified successfully."""
    token = create_refresh_token({"sub": "1", "role": "analyst"})
    payload = verify_refresh_token(token)
    assert payload["sub"] == "1"
    assert payload["type"] == "refresh"


@pytest.mark.asyncio
async def test_verify_refresh_token_invalid_type():
    """Token with wrong type is rejected."""
    access_token = create_access_token({"sub": "1", "role": "analyst"})
    with pytest.raises(Exception) as exc_info:
        verify_refresh_token(access_token)
    assert exc_info.value.status_code == 401


@pytest.mark.asyncio
async def test_token_expired(client):
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

    response = await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {expired_token}"})
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_token_exchange_returns_refresh_token(client):
    """Token exchange endpoint returns both access and refresh tokens."""
    # In test mode, token exchange creates a mock user
    response = await client.post(
        "/api/v1/auth/token",
        json={
            "code": "test-code",
            "code_verifier": "test-verifier",
            "redirect_uri": settings.OIDC_REDIRECT_URI,
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["token_type"] == "bearer"
    assert data["expires_in"] == settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60


@pytest.mark.asyncio
async def test_refresh_endpoint_returns_new_refresh_token(test_user, client):
    """Refresh endpoint returns both new access and new refresh token (rotation)."""
    # Create a refresh token for the test user
    refresh_token = create_refresh_token({"sub": str(test_user.id), "keycloak_id": test_user.keycloak_id, "role": test_user.role.value})
    
    response = await client.post(
        "/api/v1/auth/refresh",
        headers={"Authorization": f"Bearer {refresh_token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["token_type"] == "bearer"
    assert data["expires_in"] == settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
    
    # Verify new tokens work
    new_access = data["access_token"]
    me_response = await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {new_access}"})
    assert me_response.status_code == 200


@pytest.mark.asyncio
async def test_refresh_with_invalid_token(client):
    """Refresh endpoint rejects invalid refresh token."""
    response = await client.post(
        "/api/v1/auth/refresh",
        headers={"Authorization": "Bearer invalid-token"},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_refresh_with_access_token_fails(test_user, client):
    """Refresh endpoint rejects access token (must use refresh token)."""
    access_token = create_access_token({"sub": str(test_user.id), "keycloak_id": test_user.keycloak_id, "role": test_user.role.value})
    response = await client.post(
        "/api/v1/auth/refresh",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert response.status_code == 401
