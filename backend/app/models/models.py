from datetime import datetime, timezone
from sqlalchemy.ext.hybrid import hybrid_property
from typing import Optional, List
from sqlalchemy import (
    String,
    Text,
    DateTime,
    ForeignKey,
    Enum as SQLEnum,
    Integer,
    Boolean,
    JSON,
    Index,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.sqlite import JSON as SQLiteJSON
import enum
from app.core.database import Base


class AuditRunStatus(str, enum.Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class AuditProfile(str, enum.Enum):
    QUICK = "quick"
    STANDARD = "standard"
    DEEP = "deep"


class FindingStatus(str, enum.Enum):
    PLANNED = "planned"
    IN_PROGRESS = "in_progress"
    CONFIRMED = "confirmed"
    NEEDS_VALIDATION = "needs_validation"
    REJECTED = "rejected"
    DEFERRED = "deferred"
    OUT_OF_SCOPE = "out_of_scope"


class FindingSeverity(str, enum.Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"
    HARDENING = "hardening"


class UserRole(str, enum.Enum):
    VIEWER = "viewer"
    ANALYST = "analyst"
    ADMIN = "admin"


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    keycloak_id: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    username: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    full_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    role: Mapped[UserRole] = mapped_column(SQLEnum(UserRole), default=UserRole.VIEWER, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)
    last_login: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    audit_runs: Mapped[List["AuditRun"]] = relationship(back_populates="owner", lazy="selectin")

class AuditRun(Base):
    __tablename__ = "audit_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    owner_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    target_path: Mapped[str] = mapped_column(String(1024), nullable=False)
    target_type: Mapped[str] = mapped_column(String(64), nullable=False)
    profile: Mapped[AuditProfile] = mapped_column(SQLEnum(AuditProfile), default=AuditProfile.QUICK, nullable=False)
    status: Mapped[AuditRunStatus] = mapped_column(SQLEnum(AuditRunStatus), default=AuditRunStatus.PENDING, nullable=False)
    current_phase: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_phases: Mapped[int] = mapped_column(Integer, default=5, nullable=False)
    config: Mapped[dict] = mapped_column(SQLiteJSON, default=dict, nullable=False)
    run_metadata: Mapped[dict] = mapped_column("metadata", SQLiteJSON, default=dict, nullable=False)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    owner: Mapped["User"] = relationship(back_populates="audit_runs", lazy="selectin")
    findings: Mapped[List["Finding"]] = relationship(back_populates="audit_run", lazy="selectin", cascade="all, delete-orphan")
    coverage_units: Mapped[List["CoverageUnit"]] = relationship(back_populates="audit_run", lazy="selectin", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_audit_runs_owner_status", "owner_id", "status"),
        Index("ix_audit_runs_created_at", "created_at"),
    )


class Finding(Base):
    __tablename__ = "findings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    finding_id: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    audit_run_id: Mapped[int] = mapped_column(Integer, ForeignKey("audit_runs.id", ondelete="CASCADE"), nullable=False)
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    severity: Mapped[FindingSeverity] = mapped_column(SQLEnum(FindingSeverity), nullable=False)
    status: Mapped[FindingStatus] = mapped_column(SQLEnum(FindingStatus), default=FindingStatus.PLANNED, nullable=False)
    attack_class: Mapped[str] = mapped_column(String(128), nullable=False)
    file_path: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True)
    line_start: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    line_end: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    evidence: Mapped[dict] = mapped_column(SQLiteJSON, default=dict, nullable=False)
    remediation: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    tags: Mapped[List[str]] = mapped_column(SQLiteJSON, default=list, nullable=False)
    verifier_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)
    confirmed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    audit_run: Mapped["AuditRun"] = relationship(back_populates="findings", lazy="selectin")
    coverage_unit_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("coverage_units.id"), nullable=True)

    __table_args__ = (
        Index("ix_findings_audit_run_status", "audit_run_id", "status"),
        Index("ix_findings_severity", "severity"),
    )


class CoverageUnit(Base):
    __tablename__ = "coverage_units"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    unit_id: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    audit_run_id: Mapped[int] = mapped_column(Integer, ForeignKey("audit_runs.id", ondelete="CASCADE"), nullable=False)
    phase: Mapped[int] = mapped_column(Integer, nullable=False)
    hunter_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    target_files: Mapped[List[str]] = mapped_column(SQLiteJSON, default=list, nullable=False)
    invariant: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="planned", nullable=False)
    method: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    result: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    artifacts: Mapped[List[dict]] = mapped_column(SQLiteJSON, default=list, nullable=False)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    audit_run: Mapped["AuditRun"] = relationship(back_populates="coverage_units", lazy="selectin")

    __table_args__ = (
        Index("ix_coverage_units_audit_run_phase", "audit_run_id", "phase"),
        Index("ix_coverage_units_status", "status"),
    )


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    audit_run_id: Mapped[int] = mapped_column(Integer, ForeignKey("audit_runs.id", ondelete="CASCADE"), nullable=False)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    event_data: Mapped[dict] = mapped_column(SQLiteJSON, default=dict, nullable=False)
    user_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    __table_args__ = (
        Index("ix_audit_logs_audit_run_created", "audit_run_id", "created_at"),
    )