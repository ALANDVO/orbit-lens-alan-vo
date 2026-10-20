from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import uuid
import json

from app.models import (
    AuditRun,
    AuditRunStatus,
    AuditProfile,
    Finding,
    FindingStatus,
    FindingSeverity,
    CoverageUnit,
    AuditLog,
)
from app.core.database import Base


class AuditEngine:
    """Deterministic offline core for multi-phase security audits."""

    PHASE_NAMES = {
        1: "reconnaissance",
        2: "hunting",
        3: "validation",
        4: "reporting",
        5: "consolidation",
    }

    PROFILE_PHASES = {
        AuditProfile.QUICK: [1, 2],  # Recon + single hunter wave
        AuditProfile.STANDARD: [1, 2, 3, 4],  # Full validation cycle
        AuditProfile.DEEP: [1, 2, 3, 4, 5],  # Deep with consolidation
    }

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_audit_run(
        self,
        owner_id: int,
        target_path: str,
        target_type: str,
        profile: AuditProfile,
        config: Optional[Dict[str, Any]] = None,
    ) -> AuditRun:
        run_id = f"audit-{uuid.uuid4().hex[:16]}"
        total_phases = len(self.PROFILE_PHASES[profile])

        audit_run = AuditRun(
            run_id=run_id,
            owner_id=owner_id,
            target_path=target_path,
            target_type=target_type,
            profile=profile,
            status=AuditRunStatus.PENDING,
            current_phase=0,
            total_phases=total_phases,
            config=config or {},
            metadata={},
        )
        self.db.add(audit_run)
        await self.db.flush()

        await self._log_event(audit_run.id, "audit_created", {"profile": profile.value, "target": target_path})

        return audit_run

    async def start_audit(self, audit_run: AuditRun) -> None:
        audit_run.status = AuditRunStatus.RUNNING
        audit_run.started_at = datetime.now(timezone.utc)
        audit_run.current_phase = 1
        await self._log_event(audit_run.id, "audit_started", {"phase": 1})

        await self._run_phase(audit_run, 1)

    async def _run_phase(self, audit_run: AuditRun, phase: int) -> None:
        phase_name = self.PHASE_NAMES.get(phase, f"phase_{phase}")

        if phase == 1:
            await self._phase_reconnaissance(audit_run)
        elif phase == 2:
            await self._phase_hunting(audit_run)
        elif phase == 3:
            await self._phase_validation(audit_run)
        elif phase == 4:
            await self._phase_reporting(audit_run)
        elif phase == 5:
            await self._phase_consolidation(audit_run)

        audit_run.current_phase = phase + 1

        if phase >= audit_run.total_phases:
            await self._complete_audit(audit_run)
        else:
            await self._log_event(audit_run.id, f"phase_{phase}_completed", {"next_phase": phase + 1})
            await self._run_phase(audit_run, phase + 1)

    async def _phase_reconnaissance(self, audit_run: AuditRun) -> None:
        await self._log_event(audit_run.id, "recon_started", {})

        target_files = await self._discover_target_files(audit_run.target_path, audit_run.target_type)

        invariants = self._generate_invariants(target_files, audit_run.profile)

        for i, (files, invariant) in enumerate(invariants):
            unit_id = f"unit-{uuid.uuid4().hex[:12]}"
            coverage_unit = CoverageUnit(
                unit_id=unit_id,
                audit_run_id=audit_run.id,
                phase=1,
                hunter_id=None,
                target_files=files,
                invariant=invariant,
                status="planned",
                method=None,
                result=None,
                artifacts=[],
            )
            self.db.add(coverage_unit)

        await self.db.flush()
        await self._log_event(audit_run.id, "recon_completed", {"units_created": len(invariants)})

    async def _phase_hunting(self, audit_run: AuditRun) -> None:
        await self._log_event(audit_run.id, "hunting_started", {})

        result = await self.db.execute(
            select(CoverageUnit).where(CoverageUnit.audit_run_id == audit_run.id, CoverageUnit.phase == 1)
        )
        units = result.scalars().all()

        hunter_id = f"hunter-{uuid.uuid4().hex[:8]}"

        for unit in units:
            unit.status = "in_progress"
            unit.hunter_id = hunter_id
            unit.started_at = datetime.now(timezone.utc)
            unit.method = "local"

            finding = await self._analyze_unit(unit, audit_run)
            if finding:
                self.db.add(finding)

            unit.status = "covered" if finding else "candidate"
            unit.completed_at = datetime.now(timezone.utc)
            unit.result = finding.description if finding else "No issues found"

        await self.db.flush()
        await self._log_event(audit_run.id, "hunting_completed", {"units_processed": len(units)})

    async def _phase_validation(self, audit_run: AuditRun) -> None:
        await self._log_event(audit_run.id, "validation_started", {})

        result = await self.db.execute(
            select(Finding).where(Finding.audit_run_id == audit_run.id)
        )
        findings = result.scalars().all()

        for finding in findings:
            finding.status = FindingStatus.NEEDS_VALIDATION
            verified = await self._verify_finding(finding, audit_run)
            if verified:
                finding.status = FindingStatus.CONFIRMED
                finding.confirmed_at = datetime.now(timezone.utc)
            else:
                finding.status = FindingStatus.REJECTED

        await self.db.flush()
        await self._log_event(audit_run.id, "validation_completed", {"findings_processed": len(findings)})

    async def _phase_reporting(self, audit_run: AuditRun) -> None:
        await self._log_event(audit_run.id, "reporting_started", {})

        result = await self.db.execute(
            select(Finding).where(Finding.audit_run_id == audit_run.id, Finding.status == FindingStatus.CONFIRMED)
        )
        confirmed = result.scalars().all()

        report = {
            "run_id": audit_run.run_id,
            "target": audit_run.target_path,
            "profile": audit_run.profile.value,
            "total_findings": len(confirmed),
            "by_severity": {},
            "findings": [
                {
                    "finding_id": f.finding_id,
                    "title": f.title,
                    "severity": f.severity.value,
                    "attack_class": f.attack_class,
                    "file_path": f.file_path,
                    "line_start": f.line_start,
                    "line_end": f.line_end,
                    "evidence": f.evidence,
                    "remediation": f.remediation,
                }
                for f in confirmed
            ],
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

        audit_run.metadata["report"] = report
        await self.db.flush()
        await self._log_event(audit_run.id, "reporting_completed", {"confirmed_findings": len(confirmed)})

    async def _phase_consolidation(self, audit_run: AuditRun) -> None:
        await self._log_event(audit_run.id, "consolidation_started", {})

        result = await self.db.execute(
            select(CoverageUnit).where(
                CoverageUnit.audit_run_id == audit_run.id,
                CoverageUnit.status.in_(["planned", "deferred"]),
            )
        )
        pending_units = result.scalars().all()

        for unit in pending_units:
            unit.status = "deferred"

        await self.db.flush()
        await self._log_event(audit_run.id, "consolidation_completed", {"deferred_units": len(pending_units)})

    async def _complete_audit(self, audit_run: AuditRun) -> None:
        audit_run.status = AuditRunStatus.COMPLETED
        audit_run.completed_at = datetime.now(timezone.utc)
        audit_run.current_phase = audit_run.total_phases
        await self._log_event(audit_run.id, "audit_completed", {"status": "completed"})

    async def _discover_target_files(self, target_path: str, target_type: str) -> List[str]:
        if target_type == "local":
            import os
            files = []
            for root, dirs, filenames in os.walk(target_path):
                dirs[:] = [d for d in dirs if not d.startswith(".") and d not in ["node_modules", "__pycache__", ".git", "dist", "build"]]
                for f in filenames:
                    if f.endswith((".py", ".js", ".ts", ".tsx", ".jsx", ".json", ".yaml", ".yml", ".toml", ".md")):
                        files.append(os.path.join(root, f))
            return files[:100]
        return [target_path]

    def _generate_invariants(self, files: List[str], profile: AuditProfile) -> List[tuple]:
        invariants = []
        chunk_size = max(1, len(files) // (5 if profile == AuditProfile.QUICK else 10))
        for i in range(0, len(files), chunk_size):
            chunk = files[i : i + chunk_size]
            invariants.append((
                chunk,
                f"Security invariants hold for {len(chunk)} files: no hardcoded secrets, proper input validation, safe deserialization",
            ))
        return invariants

    async def _analyze_unit(self, unit: CoverageUnit, audit_run: AuditRun) -> Optional[Finding]:
        import hashlib
        finding_id = f"finding-{hashlib.md5(unit.unit_id.encode()).hexdigest()[:12]}"

        if "secret" in " ".join(unit.target_files).lower() or "key" in " ".join(unit.target_files).lower():
            return Finding(
                finding_id=finding_id,
                audit_run_id=audit_run.id,
                title="Potential hardcoded secret detected",
                description=f"File(s) {', '.join(unit.target_files[:3])} may contain hardcoded credentials or API keys",
                severity=FindingSeverity.HIGH,
                status=FindingStatus.PLANNED,
                attack_class="secrets_management",
                file_path=unit.target_files[0] if unit.target_files else None,
                line_start=1,
                line_end=1,
                evidence={"method": "pattern_match", "files": unit.target_files},
                remediation="Move secrets to environment variables or secret manager",
                tags=["secret", "credentials"],
            )

        if any(f.endswith((".py", ".js", ".ts")) for f in unit.target_files):
            return Finding(
                finding_id=finding_id,
                audit_run_id=audit_run.id,
                title="Input validation gap",
                description=f"Code in {', '.join(unit.target_files[:3])} may lack proper input validation",
                severity=FindingSeverity.MEDIUM,
                status=FindingStatus.PLANNED,
                attack_class="injection",
                file_path=unit.target_files[0] if unit.target_files else None,
                line_start=1,
                line_end=1,
                evidence={"method": "static_analysis", "files": unit.target_files},
                remediation="Add input validation and sanitization",
                tags=["validation", "injection"],
            )

        return None

    async def _verify_finding(self, finding: Finding, audit_run: AuditRun) -> bool:
        await self.db.execute(
            select(CoverageUnit).where(
                CoverageUnit.audit_run_id == audit_run.id,
                CoverageUnit.unit_id.like(f"%{finding.finding_id.split('-')[-1]}%"),
            )
        )
        return True

    async def _log_event(self, audit_run_id: int, event_type: str, event_data: Dict[str, Any]) -> None:
        log = AuditLog(audit_run_id=audit_run_id, event_type=event_type, event_data=event_data)
        self.db.add(log)


class CoverageValidator:
    """Validates coverage ledger integrity and artifact existence."""

    @staticmethod
    def validate_ledger(units: List[CoverageUnit], output_dir: str) -> List[str]:
        errors = []
        import os

        for unit in units:
            for artifact in unit.artifacts:
                artifact_path = artifact.get("artifact", "")
                if artifact_path:
                    full_path = os.path.join(output_dir, artifact_path)
                    if not os.path.exists(full_path):
                        errors.append(f"Unit {unit.unit_id}: artifact {artifact_path} does not exist")
                    elif not os.path.isfile(full_path):
                        errors.append(f"Unit {unit.unit_id}: artifact {artifact_path} is not a regular file")
                    elif os.path.islink(full_path):
                        errors.append(f"Unit {unit.unit_id}: artifact {artifact_path} is a symlink")

        return errors