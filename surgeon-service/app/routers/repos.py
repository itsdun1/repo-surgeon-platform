"""Repos listing + settings."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlalchemy import select

from app.db.models import Repo, DEFAULT_TENANT
from app.db.session import AsyncSessionLocal

router = APIRouter(prefix="/api/repos", tags=["repos"])


@router.get("")
async def list_repos():
    async with AsyncSessionLocal() as s:
        rows = (await s.execute(select(Repo).where(Repo.tenant_id == DEFAULT_TENANT))).scalars().all()
    return {
        "repos": [
            {
                "id": r.id,
                "full_name": r.full_name,
                "default_branch": r.default_branch,
                "language": r.language,
                "enabled": r.enabled,
                "rules": r.rules,
            }
            for r in rows
        ]
    }


class RepoUpdate(BaseModel):
    enabled: bool | None = None
    rules: dict[str, Any] | None = None
    default_branch: str | None = None


@router.patch("/{repo_id}")
async def update_repo(repo_id: str, body: RepoUpdate):
    async with AsyncSessionLocal() as s:
        r = (await s.execute(select(Repo).where(Repo.id == repo_id))).scalar_one_or_none()
        if not r:
            raise HTTPException(404, "repo not found")
        if body.enabled is not None:
            r.enabled = body.enabled
        if body.rules is not None:
            r.rules = body.rules
        if body.default_branch is not None:
            r.default_branch = body.default_branch
        await s.commit()
    return {"updated": True}
