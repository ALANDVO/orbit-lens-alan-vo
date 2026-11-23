"""Tests for coverage ledger tracking and validation."""

import pytest
import tempfile
import os
from app.services.audit_engine import CoverageValidator, AuditEngine
from app.models import AuditProfile, CoverageUnit
from sqlalchemy import select


@pytest.mark.asyncio
async def test_coverage_ledger_integrity(test_db):
    """Test that coverage units are created and tracked correctly."""
    # Create temporary directory with test files
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create test files
        test_file = os.path.join(tmpdir, "test.py")
        with open(test_file, "w") as f:
            f.write("# test file\n")
        
        secret_file = os.path.join(tmpdir, "config.py")
        with open(secret_file, "w") as f:
            f.write("API_KEY = 'secret123'\n")
        
        async with test_db() as session:
            engine = AuditEngine(session)
            
            # Create audit run
            run = await engine.create_audit_run(
                owner_id=1,
                target_path=tmpdir,
                target_type="local",
                profile=AuditProfile.QUICK,
                config={},
            )
            
            # Start audit (runs recon phase, creates coverage units)
            await engine.start_audit(run)
            await session.commit()
            
            # Query coverage units directly
            result = await session.execute(
                select(CoverageUnit).where(CoverageUnit.audit_run_id == run.id)
            )
            coverage_units = result.scalars().all()
            
            assert len(coverage_units) > 0
            assert all(unit.audit_run_id == run.id for unit in coverage_units)
            assert all(unit.phase == 1 for unit in coverage_units)
            assert all(unit.unit_id.startswith("unit-") for unit in coverage_units)
            assert all(unit.invariant for unit in coverage_units)
            assert all(isinstance(unit.target_files, list) for unit in coverage_units)


def test_coverage_validator_detects_missing_artifacts():
    """Test that CoverageValidator detects missing artifacts."""
    units = [
        CoverageUnit(
            unit_id="unit-123",
            audit_run_id=1,
            phase=1,
            hunter_id="hunter-1",
            target_files=["/tmp/test.py"],
            invariant="No hardcoded secrets",
            status="covered",
            artifacts=[{"artifact": "missing.txt", "type": "evidence"}],
        )
    ]
    
    errors = CoverageValidator.validate_ledger(units, "/tmp")
    
    assert len(errors) == 1
    assert "missing.txt" in errors[0]
    assert "does not exist" in errors[0]


def test_coverage_validator_accepts_valid_artifacts(tmp_path):
    """Test that CoverageValidator accepts valid artifacts."""
    # Create test artifact
    artifact_file = tmp_path / "evidence.txt"
    artifact_file.write_text("test evidence")
    
    units = [
        CoverageUnit(
            unit_id="unit-456",
            audit_run_id=1,
            phase=1,
            hunter_id="hunter-1",
            target_files=["/tmp/test.py"],
            invariant="No hardcoded secrets",
            status="covered",
            artifacts=[{"artifact": "evidence.txt", "type": "evidence"}],
        )
    ]
    
    errors = CoverageValidator.validate_ledger(units, str(tmp_path))
    
    assert len(errors) == 0


def test_coverage_validator_rejects_symlinks(tmp_path):
    """Test that CoverageValidator rejects symlinks."""
    # Create target file and symlink
    target = tmp_path / "target.txt"
    target.write_text("target")
    symlink = tmp_path / "link.txt"
    symlink.symlink_to(target)
    
    units = [
        CoverageUnit(
            unit_id="unit-789",
            audit_run_id=1,
            phase=1,
            hunter_id="hunter-1",
            target_files=["/tmp/test.py"],
            invariant="No hardcoded secrets",
            status="covered",
            artifacts=[{"artifact": "link.txt", "type": "evidence"}],
        )
    ]
    
    errors = CoverageValidator.validate_ledger(units, str(tmp_path))
    
    assert len(errors) == 1
    assert "symlink" in errors[0].lower()
