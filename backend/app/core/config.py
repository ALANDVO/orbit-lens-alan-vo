from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional
import secrets


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Application
    APP_NAME: str = "orbit-lens"
    APP_VERSION: str = "1.0.0"
    ENVIRONMENT: str = "development"
    DEBUG: bool = True

    # Server
    HOST: str = "127.0.0.1"
    PORT: int = 8000

    # Database
    DATABASE_URL: str = "sqlite+aiosqlite:///./orbit_lens.db"

    # Security
    SECRET_KEY: str = secrets.token_urlsafe(32)
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # OIDC/Keycloak
    OIDC_ISSUER_URL: str = "http://127.0.0.1:8080/realms/orbit-lens"
    OIDC_CLIENT_ID: str = "orbit-lens"
    OIDC_CLIENT_SECRET: str = ""
    OIDC_REDIRECT_URI: str = "http://127.0.0.1:3000/callback"
    OIDC_SCOPES: str = "openid profile email roles"

    # LLM Providers (optional)
    LLM_API_KEY: Optional[str] = None
    LLM_PROVIDER: Optional[str] = None  # openai, anthropic, gemini, ollama
    LLM_MODEL: Optional[str] = None
    LLM_BASE_URL: Optional[str] = None

    # CORS
    CORS_ORIGINS: list[str] = ["http://127.0.0.1:3000", "http://localhost:3000"]

    # Demo mode (local only)
    DEMO_MODE: bool = False


settings = Settings()