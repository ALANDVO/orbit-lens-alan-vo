import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.core.auth import create_access_token
from app.models import User, UserRole


async def get_test_client():
    transport = ASGITransport(app=app)
    return AsyncClient(transport=transport, base_url="http://test")


@pytest.mark.asyncio
async def test_create_audit_run(test_user, auth_client):
    response = await auth_client.post("/api/v1/audits", json={
        "target_path": "/tmp/test-project",
        "target_type": "local",
        "profile": "quick",
        "config": {"test": True}
    })
    assert response.status_code == 201
    data = response.json()
    assert data["target_path"] == "/tmp/test-project"
    assert data["target_type"] == "local"
    assert data["profile"] == "quick"
    assert data["status"] == "pending"
    assert "run_id" in data


@pytest.mark.asyncio
async def test_list_audit_runs(test_user, auth_client):
    await auth_client.post("/api/v1/audits", json={
        "target_path": "/tmp/test1",
        "target_type": "local",
        "profile": "quick",
    })
    await auth_client.post("/api/v1/audits", json={
        "target_path": "/tmp/test2",
        "target_type": "local",
        "profile": "standard",
    })

    response = await auth_client.get("/api/v1/audits")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 2
    assert len(data["items"]) == 2


@pytest.mark.asyncio
async def test_get_audit_run(test_user, auth_client):
    create_resp = await auth_client.post("/api/v1/audits", json={
        "target_path": "/tmp/test-get",
        "target_type": "local",
        "profile": "quick",
    })
    run_id = create_resp.json()["run_id"]

    response = await auth_client.get(f"/api/v1/audits/{run_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["run_id"] == run_id


@pytest.mark.asyncio
async def test_start_audit_run(test_user, auth_client):
    create_resp = await auth_client.post("/api/v1/audits", json={
        "target_path": "/tmp/test-start",
        "target_type": "local",
        "profile": "quick",
    })
    run_id = create_resp.json()["run_id"]

    response = await auth_client.post(f"/api/v1/audits/{run_id}/start")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "completed"
    assert data["current_phase"] == data["total_phases"]


@pytest.mark.asyncio
async def test_get_findings(test_user, auth_client):
    create_resp = await auth_client.post("/api/v1/audits", json={
        "target_path": "/tmp/test-findings",
        "target_type": "local",
        "profile": "quick",
    })
    run_id = create_resp.json()["run_id"]
    await auth_client.post(f"/api/v1/audits/{run_id}/start")

    response = await auth_client.get(f"/api/v1/audits/{run_id}/findings")
    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    assert "total" in data


@pytest.mark.asyncio
async def test_get_coverage(test_user, auth_client):
    create_resp = await auth_client.post("/api/v1/audits", json={
        "target_path": "/tmp/test-coverage",
        "target_type": "local",
        "profile": "quick",
    })
    run_id = create_resp.json()["run_id"]
    await auth_client.post(f"/api/v1/audits/{run_id}/start")

    response = await auth_client.get(f"/api/v1/audits/{run_id}/coverage")
    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    assert "total" in data


@pytest.mark.asyncio
async def test_export_json(test_user, auth_client):
    create_resp = await auth_client.post("/api/v1/audits", json={
        "target_path": "/tmp/test-export",
        "target_type": "local",
        "profile": "quick",
    })
    run_id = create_resp.json()["run_id"]
    await auth_client.post(f"/api/v1/audits/{run_id}/start")

    response = await auth_client.get(f"/api/v1/audits/{run_id}/export?format=json")
    assert response.status_code == 200
    data = response.json()
    assert data["run_id"] == run_id
    assert "findings" in data
    assert "coverage" in data


@pytest.mark.asyncio
async def test_export_sarif(test_user, auth_client):
    create_resp = await auth_client.post("/api/v1/audits", json={
        "target_path": "/tmp/test-sarif",
        "target_type": "local",
        "profile": "quick",
    })
    run_id = create_resp.json()["run_id"]
    await auth_client.post(f"/api/v1/audits/{run_id}/start")

    response = await auth_client.get(f"/api/v1/audits/{run_id}/export?format=sarif")
    assert response.status_code == 200
    data = response.json()
    assert data["version"] == "2.1.0"
    assert "runs" in data


@pytest.mark.asyncio
async def test_unauthorized_access():
    async with await get_test_client() as client:
        response = await client.get("/api/v1/audits")
        assert response.status_code == 401


@pytest.mark.asyncio
async def test_forbidden_delete(test_user, auth_client):
    create_resp = await auth_client.post("/api/v1/audits", json={
        "target_path": "/tmp/test-delete",
        "target_type": "local",
        "profile": "quick",
    })
    run_id = create_resp.json()["run_id"]

    response = await auth_client.delete(f"/api/v1/audits/{run_id}")
    assert response.status_code == 403
