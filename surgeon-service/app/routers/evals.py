"""Evals API — read eval results from DB."""
from __future__ import annotations

from fastapi import APIRouter
from sqlalchemy import desc, select

from app.db.models import EvalRun
from app.db.session import AsyncSessionLocal

router = APIRouter(prefix="/api/evals", tags=["evals"])


@router.get("")
async def list_evals(suite: str | None = None, runtime: str | None = None, limit: int = 100):
    async with AsyncSessionLocal() as s:
        q = select(EvalRun).order_by(desc(EvalRun.created_at)).limit(min(limit, 500))
        if suite:
            q = q.where(EvalRun.suite == suite)
        if runtime:
            q = q.where(EvalRun.runtime == runtime)
        rows = (await s.execute(q)).scalars().all()
    return {
        "evals": [
            {
                "id": r.id,
                "fixture_id": r.fixture_id,
                "suite": r.suite,
                "runtime": r.runtime,
                "passed": r.passed,
                "score": float(r.score) if r.score is not None else None,
                "latency_ms": r.latency_ms,
                "cost_usd": float(r.cost_usd) if r.cost_usd else None,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in rows
        ]
    }
