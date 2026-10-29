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
from app.core.auth import (
    create_access_token,
    create_refresh_token,
    verify_oidc_token,
    verify_refresh_token,
    security,
    reset_oidc_cache,
)


router = APIRouter(prefix="/api/v1/auth", tags=["auth"])

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: AsyncSession = Depends(get_db),
) -> User:
    if not credentials:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")

    try:
        payload = jwt.decode(credentials.credentials, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    except JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

    keycloak_id = payload.get("keycloak_id") or payload.get("sub")
    if not keycloak_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token payload")

    result = await db.execute(select(User).where(User.keycloak_id == keycloak_id))
    user = result.scalar_one_or_none()
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


@router.get("/login")
async def login():
    from app.core.auth import get_oidc_config
    config = await get_oidc_config()
    return {
        "authorization_endpoint": config.get("authorization_endpoint", ""),
        "client_id": settings.OIDC_CLIENT_ID,
        "redirect_uri": settings.OIDC_REDIRECT_URI,
        "scopes": settings.OIDC_SCOPES.split(),
    }


class TokenExchangeRequest(BaseModel):
    code: str
    code_verifier: str
    redirect_uri: str


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


@router.post("/token", response_model=TokenResponse)
async def token_exchange(
    request: TokenExchangeRequest,
    db: AsyncSession = Depends(get_db),
):
    from app.core.auth import get_oidc_config
    config = await get_oidc_config()
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            config["token_endpoint"],
            data={
                "grant_type": "authorization_code",
                "client_id": settings.OIDC_CLIENT_ID,
                "client_secret": settings.OIDC_CLIENT_SECRET,
                "code": request.code,
                "redirect_uri": request.redirect_uri,
                "code_verifier": request.code_verifier,
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        if resp.status_code != 200:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Token exchange failed")
        tokens = resp.json()

    access_token = tokens["access_token"]
    payload = await verify_oidc_token(access_token)

    keycloak_id = payload.get("sub")
    email = payload.get("email")
    username = payload.get("preferred_username", email)
    full_name = payload.get("name")
    roles = payload.get("realm_access", {}).get("roles", [])

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
    payload = verify_refresh_token(credentials.credentials)

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


