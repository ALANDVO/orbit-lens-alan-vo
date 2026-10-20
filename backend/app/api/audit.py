from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from typing import Optional, List
from pydantic import BaseModel, Field, computed_field
from datetime import datetime, timezone
import uuid

from app.core.database import get_db
from app.api.auth import get_current_user, get_current_user_optional
from app.models import User, UserRole, AuditRun, AuditRunStatus, AuditProfile, Finding, FindingStatus, FindingSeverity, CoverageUnit, AuditLog
from app.services.audit_engine import AuditEngine


router = APIRouter(prefix="/api/v1/audits", tags=["audits"])


class AuditRunCreate(BaseModel):
    target_path: str = Field(..., min_length=1, max_length=1024)
    target_type: str = Field(..., pattern="^(local|git|archive)$")
    profile: AuditProfile = AuditProfile.QUICK
    config: Optional[dict] = None


class AuditRunResponse(BaseModel):
    id: int
    run_id: str
    owner_id: int
    target_path: str
    target_type: str
    profile: AuditProfile
    status: AuditRunStatus
    current_phase: int
    total_phases: int
    config: dict
    run_metadata: dict
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

    @computed_field
    @property
    def metadata(self) -> dict:
        return self.run_metadata

class PaginatedAuditRunResponse(BaseModel):
    items: List[AuditRunResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


class FindingResponse(BaseModel):
    id: int
    finding_id: str
    audit_run_id: int
    title: str
    description: str
    severity: FindingSeverity
    status: FindingStatus
    attack_class: str
    file_path: Optional[str]
    line_start: Optional[int]
    line_end: Optional[int]
    evidence: dict
    remediation: Optional[str]
    tags: List[str]
    verifier_notes: Optional[str]
    created_at: datetime
    updated_at: datetime
    confirmed_at: Optional[datetime]

    class Config:
        from_attributes = True


class PaginatedFindingResponse(BaseModel):
    items: List[FindingResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


class CoverageUnitResponse(BaseModel):
    id: int
    unit_id: str
    audit_run_id: int
    phase: int
    hunter_id: Optional[str]
    target_files: List[str]
    invariant: str
    status: str
    method: Optional[str]
    result: Optional[str]
    artifacts: List[dict]
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class PaginatedCoverageResponse(BaseModel):
    items: List[CoverageUnitResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


@router.post("", response_model=AuditRunResponse, status_code=status.HTTP_201_CREATED)
async def create_audit_run(
    data: AuditRunCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if user.role not in [UserRole.ANALYST, UserRole.ADMIN]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")

    engine = AuditEngine(db)
    audit_run = await engine.create_audit_run(
        owner_id=user.id,
        target_path=data.target_path,
        target_type=data.target_type,
        profile=data.profile,
        config=data.config,
    )
    await db.commit()
    await db.refresh(audit_run)
    return audit_run


@router.get("", response_model=PaginatedAuditRunResponse)
async def list_audit_runs(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status_filter: Optional[AuditRunStatus] = Query(None, alias="status"),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    query = select(AuditRun).where(AuditRun.owner_id == user.id)
    if status_filter:
        query = query.where(AuditRun.status == status_filter)

    query = query.order_by(AuditRun.created_at.desc())

    count_query = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_query)).scalar() or 0

    query = query.offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(query)
    items = result.scalars().all()

    return PaginatedAuditRunResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=(total + page_size - 1) // page_size,
    )


@router.get("/{run_id}", response_model=AuditRunResponse)
async def get_audit_run(
    run_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(AuditRun).where(AuditRun.run_id == run_id, AuditRun.owner_id == user.id))
    audit_run = result.scalar_one_or_none()
    if not audit_run:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Audit run not found")
    return audit_run


@router.delete("/{run_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_audit_run(
    run_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if user.role != UserRole.ADMIN:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin only")

    result = await db.execute(select(AuditRun).where(AuditRun.run_id == run_id))
    audit_run = result.scalar_one_or_none()
    if not audit_run:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Audit run not found")

    await db.delete(audit_run)
    await db.commit()


@router.post("/{run_id}/start", response_model=AuditRunResponse)
async def start_audit_run(
    run_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if user.role not in [UserRole.ANALYST, UserRole.ADMIN]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")

    result = await db.execute(select(AuditRun).where(AuditRun.run_id == run_id, AuditRun.owner_id == user.id))
    audit_run = result.scalar_one_or_none()
    if not audit_run:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Audit run not found")

    if audit_run.status != AuditRunStatus.PENDING:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Audit run already started or completed")

    engine = AuditEngine(db)
    await engine.start_audit(audit_run)
    await db.commit()
    await db.refresh(audit_run)
    return audit_run


@router.get("/{run_id}/findings", response_model=PaginatedFindingResponse)
async def get_audit_findings(
    run_id: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status_filter: Optional[FindingStatus] = Query(None, alias="status"),
    severity_filter: Optional[FindingSeverity] = Query(None, alias="severity"),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(AuditRun).where(AuditRun.run_id == run_id, AuditRun.owner_id == user.id))
    audit_run = result.scalar_one_or_none()
    if not audit_run:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Audit run not found")

    query = select(Finding).where(Finding.audit_run_id == audit_run.id)
    if status_filter:
        query = query.where(Finding.status == status_filter)
    if severity_filter:
        query = query.where(Finding.severity == severity_filter)

    query = query.order_by(Finding.created_at.desc())

    count_query = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_query)).scalar() or 0

    query = query.offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(query)
    items = result.scalars().all()

    return PaginatedFindingResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=(total + page_size - 1) // page_size,
    )


@router.get("/{run_id}/coverage", response_model=PaginatedCoverageResponse)
async def get_audit_coverage(
    run_id: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status_filter: Optional[str] = Query(None, alias="status"),
    phase_filter: Optional[int] = Query(None, alias="phase"),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(AuditRun).where(AuditRun.run_id == run_id, AuditRun.owner_id == user.id))
    audit_run = result.scalar_one_or_none()
    if not audit_run:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Audit run not found")

    query = select(CoverageUnit).where(CoverageUnit.audit_run_id == audit_run.id)
    if status_filter:
        query = query.where(CoverageUnit.status == status_filter)
    if phase_filter:
        query = query.where(CoverageUnit.phase == phase_filter)

    query = query.order_by(CoverageUnit.created_at.desc())

    count_query = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_query)).scalar() or 0

    query = query.offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(query)
    items = result.scalars().all()

    return PaginatedCoverageResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=(total + page_size - 1) // page_size,
    )


@router.get("/{run_id}/export")
async def export_audit_run(
    run_id: str,
    format: str = Query("json", pattern="^(json|sarif)$"),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(AuditRun).where(AuditRun.run_id == run_id, AuditRun.owner_id == user.id))
    audit_run = result.scalar_one_or_none()
    if not audit_run:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Audit run not found")

    if format == "json":
        findings_result = await db.execute(select(Finding).where(Finding.audit_run_id == audit_run.id))
        findings = findings_result.scalars().all()

        coverage_result = await db.execute(select(CoverageUnit).where(CoverageUnit.audit_run_id == audit_run.id))
        coverage = coverage_result.scalars().all()

        return {
            "run_id": audit_run.run_id,
            "target_path": audit_run.target_path,
            "target_type": audit_run.target_type,
            "profile": audit_run.profile.value,
            "status": audit_run.status.value,
            "created_at": audit_run.created_at.isoformat(),
            "completed_at": audit_run.completed_at.isoformat() if audit_run.completed_at else None,
            "findings": [
                {
                    "finding_id": f.finding_id,
                    "title": f.title,
                    "description": f.description,
                    "severity": f.severity.value,
                    "status": f.status.value,
                    "attack_class": f.attack_class,
                    "file_path": f.file_path,
                    "line_start": f.line_start,
                    "line_end": f.line_end,
                    "evidence": f.evidence,
                    "remediation": f.remediation,
                    "tags": f.tags,
                }
                for f in findings
            ],
            "coverage": [
                {
                    "unit_id": c.unit_id,
                    "phase": c.phase,
                    "hunter_id": c.hunter_id,
                    "target_files": c.target_files,
                    "invariant": c.invariant,
                    "status": c.status,
                    "method": c.method,
                    "result": c.result,
                    "artifacts": c.artifacts,
                }
                for c in coverage
            ],
        }

    else:  # SARIF
        findings_result = await db.execute(
            select(Finding).where(Finding.audit_run_id == audit_run.id, Finding.status == FindingStatus.CONFIRMED)
        )
        findings = findings_result.scalars().all()

        sarif = {
            "version": "2.1.0",
            "$schema": "https://json.schemastore.org/sarif-2.1.0.json",
            "runs": [
                {
                    "tool": {
                        "driver": {
                            "name": "Orbit Lens",
                            "version": "1.0.0",
                            "informationUri": "https://github.com/ALANDVO/orbit-lens-alan-vo",
                        }
                    },
                    "results": [
                        {
                            "ruleId": f.attack_class,
                            "message": {"text": f.title},
                            "level": {"critical": "error", "high": "error", "medium": "warning", "low": "note", "info": "note", "hardening": "note"}.get(f.severity.value, "note"),
                            "locations": [
                                {
                                    "physicalLocation": {
                                        "artifactLocation": {"uri": f.file_path or "unknown"},
                                        "region": {"startLine": f.line_start or 1, "endLine": f.line_end or 1},
                                    }
                                }
                            ] if f.file_path else [],
                            "properties": {
                                "severity": f.severity.value,
                                "findingId": f.finding_id,
                                "description": f.description,
                                "remediation": f.remediation,
                            },
                        }
                        for f in findings
                    ],
                }
            ],
        }
        return sarif


@router.get("/{run_id}/logs")
async def get_audit_logs(
    run_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(AuditRun).where(AuditRun.run_id == run_id, AuditRun.owner_id == user.id))
    audit_run = result.scalar_one_or_none()
    if not audit_run:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Audit run not found")

    logs_result = await db.execute(
        select(AuditLog).where(AuditLog.audit_run_id == audit_run.id).order_by(AuditLog.created_at)
    )
    logs = logs_result.scalars().all()

    return [
        {
            "event_type": log.event_type,
            "event_data": log.event_data,
            "created_at": log.created_at.isoformat(),
        }
        for log in logs
    ]