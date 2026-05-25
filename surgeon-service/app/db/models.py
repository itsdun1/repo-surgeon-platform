"""SQLAlchemy 2.x async models. Single-tenant local mode; tenant_id columns kept for future."""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import JSON, BigInteger, Boolean, DateTime, ForeignKey, Index, Integer, Numeric, String, Text, UniqueConstraint, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def gen_uuid() -> str:
    return str(uuid.uuid4())


class Base(DeclarativeBase):
    pass


DEFAULT_TENANT = "local"


class Tenant(Base):
    __tablename__ = "tenants"
    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=gen_uuid)
    installation_id: Mapped[int | None] = mapped_column(BigInteger, unique=True, nullable=True)
    account_login: Mapped[str] = mapped_column(String(120))
    account_type: Mapped[str] = mapped_column(String(16), default="User")  # User | Organization
    agent_repo: Mapped[str | None] = mapped_column(String(200), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Repo(Base):
    __tablename__ = "repos"
    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=gen_uuid)
    tenant_id: Mapped[str] = mapped_column(String(64), ForeignKey("tenants.id"), default=DEFAULT_TENANT)
    full_name: Mapped[str] = mapped_column(String(200))
    default_branch: Mapped[str] = mapped_column(String(60), default="main")
    language: Mapped[str | None] = mapped_column(String(40), nullable=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    rules: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    __table_args__ = (UniqueConstraint("tenant_id", "full_name"),)


class Run(Base):
    __tablename__ = "runs"
    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=gen_uuid)
    tenant_id: Mapped[str] = mapped_column(String(64), ForeignKey("tenants.id"), default=DEFAULT_TENANT)
    repo_id: Mapped[str | None] = mapped_column(String(64), ForeignKey("repos.id"), nullable=True)
    repo_full_name: Mapped[str] = mapped_column(String(200))
    mode: Mapped[str] = mapped_column(String(40))  # bug-fix | feature | refactor | scan | manual
    status: Mapped[str] = mapped_column(String(20), default="queued")  # queued|running|success|failed|cancelled
    trigger: Mapped[str] = mapped_column(String(60))  # webhook:issues | cron | manual | eval
    trigger_payload: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    model: Mapped[str | None] = mapped_column(String(80), nullable=True)
    prompt: Mapped[str | None] = mapped_column(Text, nullable=True)
    session_branch: Mapped[str | None] = mapped_column(String(120), nullable=True)
    issue_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    pr_url: Mapped[str | None] = mapped_column(String(300), nullable=True)
    pr_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    log_path: Mapped[str | None] = mapped_column(String(300), nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    exit_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    cost_usd: Mapped[float | None] = mapped_column(Numeric(10, 4), nullable=True)
    tool_calls: Mapped[int] = mapped_column(Integer, default=0)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


Index("runs_repo_started_idx", Run.repo_full_name, Run.started_at.desc())
Index("runs_status_idx", Run.status)


class WebhookEvent(Base):
    __tablename__ = "webhook_events"
    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=gen_uuid)
    tenant_id: Mapped[str] = mapped_column(String(64), default=DEFAULT_TENANT)
    delivery_id: Mapped[str] = mapped_column(String(80), unique=True)
    event_type: Mapped[str] = mapped_column(String(60))
    action: Mapped[str | None] = mapped_column(String(60), nullable=True)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    processed: Mapped[bool] = mapped_column(Boolean, default=False)
    run_id: Mapped[str | None] = mapped_column(String(64), ForeignKey("runs.id"), nullable=True)


class EvalRun(Base):
    __tablename__ = "eval_runs"
    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=gen_uuid)
    tenant_id: Mapped[str] = mapped_column(String(64), default=DEFAULT_TENANT)
    fixture_id: Mapped[str] = mapped_column(String(120))
    suite: Mapped[str] = mapped_column(String(60))
    runtime: Mapped[str] = mapped_column(String(80))
    passed: Mapped[bool] = mapped_column(Boolean, default=False)
    assertions: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    score: Mapped[float] = mapped_column(Numeric(5, 2), default=0)
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    cost_usd: Mapped[float | None] = mapped_column(Numeric(10, 4), nullable=True)
    trace_path: Mapped[str | None] = mapped_column(String(300), nullable=True)
    run_id: Mapped[str | None] = mapped_column(String(64), ForeignKey("runs.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class MemoryAudit(Base):
    __tablename__ = "memory_audits"
    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=gen_uuid)
    tenant_id: Mapped[str] = mapped_column(String(64), default=DEFAULT_TENANT)
    repo: Mapped[str] = mapped_column(String(120))
    file_path: Mapped[str] = mapped_column(String(300))
    before_blob: Mapped[str | None] = mapped_column(Text, nullable=True)
    after_blob: Mapped[str] = mapped_column(Text)
    edited_by: Mapped[str] = mapped_column(String(120))
    pr_url: Mapped[str | None] = mapped_column(String(300), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
