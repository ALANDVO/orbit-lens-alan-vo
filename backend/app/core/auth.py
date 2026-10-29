"""OIDC authentication and authorization utilities.

Provides:
- OIDC discovery and JWKS fetching/caching
- Token verification with signature, issuer, and audience checks
- Role-based access control decorator
"""
from datetime import datetime, timezone, timedelta
from typing import Optional

import httpx
from jose import jwt, JWTError
from jose.utils import base64url_decode
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization
from fastapi import Depends, HTTPException, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from app.core.config import settings

security = HTTPBearer(auto_error=False)

# OIDC configuration cache
_oidc_config: dict = {}
_jwks: dict = {}


def reset_oidc_cache() -> None:
    """Reset the OIDC/JWKS cache. Used in tests and on config reload."""
    global _oidc_config, _jwks
    _oidc_config = {}
    _jwks = {}


def is_test_mode() -> bool:
    """Test mode skips real OIDC endpoint calls and uses local secret for JWT."""
    return settings.ENVIRONMENT == "test" or settings.DEBUG


async def get_oidc_config() -> dict:
    """Fetch and cache the OIDC discovery document."""
    global _oidc_config
    if not _oidc_config:
        if is_test_mode():
            return {"jwks_uri": "", "issuer": settings.OIDC_ISSUER_URL, "authorization_endpoint": ""}
        async with httpx.AsyncClient() as client:
            resp = await client.get(f"{settings.OIDC_ISSUER_URL}/.well-known/openid-configuration")
            resp.raise_for_status()
            _oidc_config = resp.json()
    return _oidc_config


async def get_jwks() -> dict:
    """Fetch and cache JWKS keys from the OIDC provider."""
    global _jwks
    if not _jwks:
        if is_test_mode():
            return {"keys": []}
        config = await get_oidc_config()
        async with httpx.AsyncClient() as client:
            resp = await client.get(config["jwks_uri"])
            resp.raise_for_status()
            _jwks = resp.json()
    return _jwks


def _extract_public_key(jwk: dict):
    """Extract a PEM-encoded RSA public key from a JWK."""
    public_key = rsa.RSAPublicNumbers(
        e=int.from_bytes(base64url_decode(jwk["e"]), "big"),
        n=int.from_bytes(base64url_decode(jwk["n"]), "big"),
    ).public_key()
    return public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )


async def verify_oidc_token(token: str) -> dict:
    """
    Verify a JWT token issued by the OIDC provider (Keycloak).

    Validates:
    - Signature using the provider's JWKS
    - Issuer matches OIDC_ISSUER_URL
    - Audience matches OIDC_CLIENT_ID
    - Token is not expired
    """
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing token")

    try:
        if is_test_mode():
            # In test/debug mode, accept tokens signed with the local secret
            payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
            return payload

        jwks = await get_jwks()
        unverified_header = jwt.get_unverified_header(token)
        kid = unverified_header.get("kid")
        if not kid:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token header")

        key = next((k for k in jwks["keys"] if k["kid"] == kid), None)
        if not key:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token key")

        pem = _extract_public_key(key)
        payload = jwt.decode(
            token,
            pem,
            algorithms=["RS256"],
            audience=settings.OIDC_CLIENT_ID,
            issuer=settings.OIDC_ISSUER_URL,
        )
        return payload
    except JWTError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Token validation failed: {e}",
        )


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Create an internal access token signed with the local secret."""
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire, "iat": datetime.now(timezone.utc), "type": "access"})
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def create_refresh_token(data: dict) -> str:
    """Create an internal refresh token signed with the local secret."""
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    to_encode.update({"exp": expire, "iat": datetime.now(timezone.utc), "type": "refresh"})
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def verify_refresh_token(token: str) -> dict:
    """Decode and verify a refresh token. Returns the payload or raises HTTPException."""
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        if payload.get("type") != "refresh":
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token type")
        return payload
    except JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")


def require_role(*roles: str):
    """
    FastAPI dependency decorator for role-based access control.

    Usage:
        @router.get("/admin", dependencies=[Depends(require_role("admin"))])
    """
    from app.models import User

    async def role_checker(
        credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
        db=Depends(None),
    ):
        from app.api.auth import get_current_user
        user = await get_current_user(credentials, db)  # type: ignore
        allowed = [r.lower() for r in roles]
        if user.role.value not in allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions",
            )
        return user

    return role_checker
