import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.pool import StaticPool
from app.core.database import Base, get_db
from app.main import app
from httpx import AsyncClient
from app.core.auth import create_access_token, reset_oidc_cache
from app.models import User, UserRole
from app.core.config import settings

# Set test environment
settings.ENVIRONMENT = "test"
settings.DEBUG = True
# Reset OIDC cache for test mode
reset_oidc_cache()


@pytest.fixture(scope="session")
def event_loop():
    import asyncio
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="function")
async def test_db():
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async def override_get_db():
        async with async_session() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise
            finally:
                await session.close()

    app.dependency_overrides[get_db] = override_get_db

    yield async_session

    await engine.dispose()
    app.dependency_overrides.clear()


@pytest_asyncio.fixture(scope="function")
async def test_user(test_db):
    async with test_db() as session:
        user = User(
            keycloak_id="test-user-123",
            email="test@example.com",
            username="testuser",
            full_name="Test User",
            role=UserRole.ANALYST,
            is_active=True,
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)
        return user


@pytest_asyncio.fixture(scope="function")
async def auth_headers(test_user):
    token = create_access_token({"sub": str(test_user.id), "keycloak_id": test_user.keycloak_id, "role": test_user.role.value})
    return {"Authorization": f"Bearer {token}"}


@pytest_asyncio.fixture(scope="function")
async def client(test_db):
    async with AsyncClient(app=app, base_url="http://test") as client:
        yield client