import pytest
from app.services.audit_engine import AuditEngine
from app.models import AuditProfile

@pytest.mark.asyncio
async def test_create_audit_run(test_db):
    async with test_db() as session:
        engine = AuditEngine(session)
        run = await engine.create_audit_run(
            owner_id=1,
            target_path="/tmp/test",
            target_type="local",
            profile=AuditProfile.QUICK,
            config={},
        )
        assert run.run_id.startswith("audit-")
        assert run.target_path == "/tmp/test"
        assert run.target_type == "local"
        assert run.profile == AuditProfile.QUICK
