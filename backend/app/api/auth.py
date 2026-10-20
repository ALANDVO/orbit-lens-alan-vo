from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from typing import Optional
from datetime import datetime, timezone, timedelta
from jose import jwt, JWTError
from passlib.context import CryptContext
import httpx
import uuid
from app.core.config import settings
from app.core.database import get_db
from app.models import User, UserRole


router = APIRouter(prefix="/api/v1/auth", tags=["auth"])

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
security = HTTPBearer(auto_error=False)

# OIDC configuration cache
_oidc_config: dict = {}
_jwks: dict = {}


def reset_oidc_cache() -> None:
    global _oidc_config, _jwks
    _oidc_config = {}
    _jwks = {}


def is_test_mode() -> bool:
    result = settings.ENVIRONMENT == "test" or settings.DEBUG
    print(f"DEBUG is_test_mode: {result}, ENVIRONMENT={settings.ENVIRONMENT}, DEBUG={settings.DEBUG}")
    return result


async def get_oidc_config() -> dict:
    global _oidc_config
    if not _oidc_config:
        if is_test_mode():
            print("DEBUG get_oidc_config: returning test config")
            return {"jwks_uri": ""}
        async with httpx.AsyncClient() as client:
            resp = await client.get(f"{settings.OIDC_ISSUER_URL}/.well-known/openid-configuration")
            resp.raise_for_status()
            _oidc_config = resp.json()
    return _oidc_config


async def get_jwks() -> dict:
    global _jwks
    if not _jwks:
        if is_test_mode():
            print("DEBUG get_jwks: returning empty keys")
            return {"keys": []}
        config = await get_oidc_config()
        async with httpx.AsyncClient() as client:
            resp = await client.get(config["jwks_uri"])
            resp.raise_for_status()
            _jwks = resp.json()
    return _jwks


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire, "iat": datetime.now(timezone.utc), "type": "access"})
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def create_refresh_token(data: dict) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    to_encode.update({"exp": expire, "iat": datetime.now(timezone.utc), "type": "refresh"})
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


async def verify_token(token: str) -> dict:
    try:
        if is_test_mode():
            print(f"DEBUG verify_token: test mode, decoding with local secret")
            payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
            print(f"DEBUG verify_token: payload={payload}")
            return payload
        print("DEBUG verify_token: not test mode")
        jwks = await get_jwks()
        unverified_header = jwt.get_unverified_header(token)
        kid = unverified_header.get("kid")
        if not kid:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token header")

        key = next((k for k in jwks["keys"] if k["kid"] == kid), None)
        if not key:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token key")

        from jose.utils import base64url_decode
        from cryptography.hazmat.primitives.asymmetric import rsa
        from cryptography.hazmat.primitives import serialization

        public_key = rsa.RSAPublicNumbers(
            e=int.from_bytes(base64url_decode(key["e"]), "big"),
            n=int.from_bytes(base64url_decode(key["n"]), "big"),
        ).public_key()

        pem = public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )

        payload = jwt.decode(
            token,
            pem,
            algorithms=["RS256"],
            audience=settings.OIDC_CLIENT_ID,
            issuer=settings.OIDC_ISSUER_URL,
        )
        return payload
    except JWTError as e:
        print(f"DEBUG verify_token: JWTError: {e}")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=f"Token validation failed: {e}")


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: AsyncSession = Depends(get_db),
) -> User:
    if not credentials:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")

    payload = await verify_token(credentials.credentials)
    keycloak_id = payload.get("sub")
    print(f"DEBUG get_current_user: keycloak_id from payload sub = {keycloak_id}")
    # The payload has both 'sub' (user ID) and 'keycloak_id' - use keycloak_id
    keycloak_id = payload.get("keycloak_id") or payload.get("sub")
    print(f"DEBUG get_current_user: using keycloak_id = {keycloak_id}")
    if not keycloak_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token payload")

    result = await db.execute(select(User).where(User.keycloak_id == keycloak_id))
    user = result.scalar_one_or_none()
    print(f"DEBUG get_current_user: user found = {user is not None}")
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User inactive")

    return user


async def get_current_user_optional(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: AsyncSession = Depends(get_db),
) -> Optional[User]:
    if not credentials:
        return None
    try:
        return await get_current_user(credentials, db)
    except HTTPException:
        return None


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int


class UserResponse(BaseModel):
    id: int
    keycloak_id: str
    email: str
    username: str
    full_name: Optional[str]
    role: UserRole
    is_active: bool


@router.get("/login")
async def login():
    config = await get_oidc_config()
    return {
        "authorization_endpoint": config.get("authorization_endpoint", ""),
        "client_id": settings.OIDC_CLIENT_ID,
        "redirect_uri": settings.OIDC_REDIRECT_URI,
        "scopes": settings.OIDC_SCOPES.split(),
    }


@router.post("/token", response_model=TokenResponse)
async def token_exchange(
    code: str,
    code_verifier: str,
    redirect_uri: str,
    db: AsyncSession = Depends(get_db),
):
    config = await get_oidc_config()
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            config["token_endpoint"],
            data={
                "grant_type": "authorization_code",
                "client_id": settings.OIDC_CLIENT_ID,
                "client_secret": settings.OIDC_CLIENT_SECRET,
                "code": code,
                "redirect_uri": redirect_uri,
                "code_verifier": code_verifier,
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        if resp.status_code != 200:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Token exchange failed")
        tokens = resp.json()

    access_token = tokens["access_token"]
    payload = await verify_token(access_token)

    keycloak_id = payload.get("sub")
    email = payload.get("email")
    username = payload.get("preferred_username", email)
    full_name = payload.get("name")
    roles = payload.get("roles", [])

    result = await db.execute(select(User).where(User.keycloak_id == keycloak_id))
    user = result.scalar_one_or_none()

    if not user:
        role = UserRole.ADMIN if "admin" in roles else UserRole.ANALYST if "analyst" in roles else UserRole.VIEWER
        user = User(
            keycloak_id=keycloak_id,
            email=email,
            username=username,
            full_name=full_name,
            role=role,
        )
        db.add(user)
        await db.flush()
    else:
        user.email = email
        user.username = username
        user.full_name = full_name
        if "admin" in roles:
            user.role = UserRole.ADMIN
        elif "analyst" in roles:
            user.role = UserRole.ANALYST
        else:
            user.role = UserRole.VIEWER
        user.last_login = datetime.now(timezone.utc)

    await db.commit()

    internal_access = create_access_token({"sub": str(user.id), "keycloak_id": user.keycloak_id, "role": user.role.value})
    internal_refresh = create_refresh_token({"sub": str(user.id), "keycloak_id": user.keycloak_id})

    return TokenResponse(
        access_token=internal_access,
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db),
):
    try:
        payload = jwt.decode(credentials.credentials, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        if payload.get("type") != "refresh":
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token type")
    except JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")

    user_id = payload.get("sub")
    keycloak_id = payload.get("keycloak_id")
    result = await db.execute(select(User).where(User.id == int(user_id), User.keycloak_id == keycloak_id))
    user = result.scalar_one_or_none()
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found or inactive")

    internal_access = create_access_token({"sub": str(user.id), "keycloak_id": user.keycloak_id, "role": user.role.value})
    internal_refresh = create_refresh_token({"sub": str(user.id), "keycloak_id": user.keycloak_id})

    return TokenResponse(
        access_token=internal_access,
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


@router.get("/me", response_model=UserResponse)
async def get_me(user: User = Depends(get_current_user)):
    return UserResponse(
        id=user.id,
        keycloak_id=user.keycloak_id,
        email=user.email,
        username=user.username,
        full_name=user.full_name,
        role=user.role,
        is_active=user.is_active,
    )


@router.post("/logout")
async def logout(user: User = Depends(get_current_user)):
    return {"message": "Logged out successfully"}


@router.get("/config")
async def auth_config():
    return {
        "issuer": settings.OIDC_ISSUER_URL,
        "client_id": settings.OIDC_CLIENT_ID,
        "redirect_uri": settings.OIDC_REDIRECT_URI,
        "scopes": settings.OIDC_SCOPES.split(),
    }