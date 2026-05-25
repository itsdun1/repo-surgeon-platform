"""POST /webhooks/github — HMAC verify, dedupe, classify, persist, enqueue."""
from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, Header, HTTPException, Request
from sqlalchemy import select

from app.db.models import Repo, Run, WebhookEvent, DEFAULT_TENANT
from app.db.session import AsyncSessionLocal
from app.services import classifier, github_app, queue
from app.services.webhook_verify import verify_github_signature

router = APIRouter(prefix="/webhooks", tags=["webhooks"])


@router.post("/github")
async def github_webhook(
    request: Request,
    x_hub_signature_256: str | None = Header(default=None),
    x_github_event: str | None = Header(default=None),
    x_github_delivery: str | None = Header(default=None),
):
    body = await request.body()
    if not verify_github_signature(body, x_hub_signature_256):
        raise HTTPException(status_code=401, detail="bad signature")
    if not x_github_event or not x_github_delivery:
        raise HTTPException(status_code=400, detail="missing event headers")

    # Dedupe
    is_new = await queue.dedupe_event(x_github_delivery)
    if not is_new:
        return {"skipped": "duplicate delivery"}

    payload = json.loads(body)
    action = payload.get("action")

    # Persist raw event
    async with AsyncSessionLocal() as s:
        evt = WebhookEvent(
            delivery_id=x_github_delivery,
            event_type=x_github_event,
            action=action,
            payload=payload,
        )
        s.add(evt)
        await s.commit()

    # Classify
    classified = classifier.classify(x_github_event, payload)
    if not classified:
        return {"skipped": f"event {x_github_event}/{action} not actionable"}

    # Mint installation token
    installation_id = classified.get("installation_id")
    if not installation_id:
        return {"skipped": "no installation_id in payload"}

    try:
        token, _ = await github_app.mint_installation_token(
            int(installation_id), redis_client=queue.get_redis()
        )
    except Exception as e:
        return {"skipped": f"could not mint token: {e}"}

    # Ensure repo row exists
    async with AsyncSessionLocal() as s:
        repo_full = classified["repo"]
        existing = await s.execute(
            select(Repo).where(Repo.tenant_id == DEFAULT_TENANT, Repo.full_name == repo_full)
        )
        repo_row = existing.scalar_one_or_none()
        if not repo_row:
            repo_row = Repo(full_name=repo_full)
            s.add(repo_row)
            await s.commit()
            await s.refresh(repo_row)

        # Create run record (queued)
        run = Run(
            repo_id=repo_row.id,
            repo_full_name=repo_full,
            mode=classified["mode"],
            status="queued",
            trigger=f"webhook:{x_github_event}",
            trigger_payload={"action": action, "delivery_id": x_github_delivery},
            issue_number=classified.get("issue_number"),
        )
        s.add(run)
        await s.commit()
        await s.refresh(run)

    # Enrich job with full issue/PR context so the agent doesn't need to fetch it.
    issue_payload = payload.get("issue") or {}
    pr_payload = payload.get("pull_request") or {}
    job = {
        "run_id": run.id,
        "mode": classified["mode"],
        "repo": classified["repo"],
        "repo_id": repo_row.id,
        "issue_number": classified.get("issue_number"),
        "pr_number": classified.get("pr_number"),
        "installation_id": installation_id,
        "github_token": token,
        "issue_title": issue_payload.get("title") or pr_payload.get("title"),
        "issue_body": issue_payload.get("body") or pr_payload.get("body") or "",
        "issue_labels": [l.get("name") for l in issue_payload.get("labels", [])] or [l.get("name") for l in pr_payload.get("labels", [])],
        "issue_url": issue_payload.get("html_url") or pr_payload.get("html_url"),
    }
    await queue.enqueue(repo_row.id, job)

    return {"queued": True, "run_id": run.id, "mode": classified["mode"]}
