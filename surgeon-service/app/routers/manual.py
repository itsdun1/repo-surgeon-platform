"""Manual trigger — fire an agent run from the dashboard."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlalchemy import select

from app.db.models import Repo, Run, DEFAULT_TENANT
from app.db.session import AsyncSessionLocal
from app.services import github_app, queue

router = APIRouter(prefix="/api", tags=["manual"])


class ManualTriggerRequest(BaseModel):
    repo: str  # "owner/name"
    mode: str  # bug-fix | feature | scan | refactor | manual:<x>
    prompt: str | None = None
    issue_number: int | None = None
    model: str | None = None
    installation_id: int


@router.post("/manual-trigger")
async def manual_trigger(req: ManualTriggerRequest):
    # Mint a fresh token
    try:
        token, _ = await github_app.mint_installation_token(req.installation_id, queue.get_redis())
    except Exception as e:
        raise HTTPException(500, f"could not mint token: {e}") from e

    async with AsyncSessionLocal() as s:
        repo_row = (
            await s.execute(
                select(Repo).where(Repo.tenant_id == DEFAULT_TENANT, Repo.full_name == req.repo)
            )
        ).scalar_one_or_none()
        if not repo_row:
            repo_row = Repo(full_name=req.repo)
            s.add(repo_row)
            await s.commit()
            await s.refresh(repo_row)

        run = Run(
            repo_id=repo_row.id,
            repo_full_name=req.repo,
            mode=req.mode,
            status="queued",
            trigger="manual",
            trigger_payload={"prompt": req.prompt} if req.prompt else None,
            model=req.model,
            issue_number=req.issue_number,
            prompt=req.prompt,
        )
        s.add(run)
        await s.commit()
        await s.refresh(run)

    job = {
        "run_id": run.id,
        "mode": req.mode,
        "repo": req.repo,
        "repo_id": repo_row.id,
        "issue_number": req.issue_number,
        "installation_id": req.installation_id,
        "github_token": token,
        "manual_prompt": req.prompt,
    }
    await queue.enqueue(repo_row.id, job)
    return {"queued": True, "run_id": run.id}
