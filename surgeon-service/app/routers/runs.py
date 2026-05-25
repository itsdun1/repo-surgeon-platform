"""Runs API."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from sqlalchemy import desc, select

from app.db.models import Run
from app.db.session import AsyncSessionLocal

router = APIRouter(prefix="/api", tags=["runs"])


@router.get("/agents/runs")
async def list_runs(repo: str | None = None, status: str | None = None, limit: int = 50):
    async with AsyncSessionLocal() as s:
        q = select(Run).order_by(desc(Run.created_at)).limit(min(limit, 200))
        if repo:
            q = q.where(Run.repo_full_name == repo)
        if status:
            q = q.where(Run.status == status)
        rows = (await s.execute(q)).scalars().all()
    return {
        "runs": [
            {
                "id": r.id,
                "repo": r.repo_full_name,
                "mode": r.mode,
                "status": r.status,
                "trigger": r.trigger,
                "model": r.model,
                "started_at": r.started_at.isoformat() if r.started_at else None,
                "finished_at": r.finished_at.isoformat() if r.finished_at else None,
                "cost_usd": float(r.cost_usd) if r.cost_usd else None,
                "pr_url": r.pr_url,
                "pr_number": r.pr_number,
                "issue_number": r.issue_number,
                "tool_calls": r.tool_calls,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in rows
        ]
    }


@router.get("/runs/{run_id}")
async def get_run(run_id: str):
    async with AsyncSessionLocal() as s:
        r = (await s.execute(select(Run).where(Run.id == run_id))).scalar_one_or_none()
    if not r:
        raise HTTPException(404, "run not found")
    return {
        "id": r.id,
        "repo": r.repo_full_name,
        "mode": r.mode,
        "status": r.status,
        "trigger": r.trigger,
        "model": r.model,
        "prompt": r.prompt,
        "session_branch": r.session_branch,
        "started_at": r.started_at.isoformat() if r.started_at else None,
        "finished_at": r.finished_at.isoformat() if r.finished_at else None,
        "exit_code": r.exit_code,
        "cost_usd": float(r.cost_usd) if r.cost_usd else None,
        "tool_calls": r.tool_calls,
        "pr_url": r.pr_url,
        "pr_number": r.pr_number,
        "issue_number": r.issue_number,
        "log_path": r.log_path,
        "error": r.error,
        "created_at": r.created_at.isoformat() if r.created_at else None,
    }
