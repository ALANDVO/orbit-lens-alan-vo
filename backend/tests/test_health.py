import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app


async def get_test_client():
    transport = ASGITransport(app=app)
    return AsyncClient(transport=transport, base_url="http://test")


@pytest.mark.asyncio
async def test_health_check():
    async with await get_test_client() as client:
        response = await client.get("/api/v1/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "version" in data
        assert "timestamp" in data


@pytest.mark.asyncio
async def test_health_db():
    async with await get_test_client() as client:
        response = await client.get("/api/v1/health/db")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["database"] == "connected"


@pytest.mark.asyncio
async def test_root():
    async with await get_test_client() as client:
        response = await client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "orbit-lens"
        assert "version" in data
