"""Periodic cleanup: old logs, old run records, orphaned workspaces.

Wired into the FastAPI lifespan via APScheduler.
"""
from __future__ import annotations

import logging
import shutil
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

from sqlalchemy import delete, select

from app.config import settings
from app.db.models import Run, WebhookEvent
from app.db.session import AsyncSessionLocal

log = logging.getLogger("surgeon.cleanup")

LOG_RETENTION_DAYS = 7
RUN_RETENTION_DAYS_FAILED = 7  # delete failed runs after 7 days
RUN_RETENTION_DAYS_SUCCESS = 30  # delete success runs after 30 days
WORKSPACE_TTL_HOURS = 1  # orphaned workspaces > 1h old


async def cleanup_old_logs() -> dict:
    """Delete log files older than LOG_RETENTION_DAYS."""
    log_root = Path(settings.log_root).expanduser()
    if not log_root.is_absolute():
        # resolve relative to monorepo root via the helper we added
        from app.config import _REPO_ROOT
        log_root = (_REPO_ROOT / log_root).resolve()
    if not log_root.exists():
        return {"deleted": 0, "skipped": "log root missing"}
    cutoff = time.time() - LOG_RETENTION_DAYS * 86400
    deleted = 0
    for f in log_root.glob("*.log"):
        try:
            if f.stat().st_mtime < cutoff:
                f.unlink()
                deleted += 1
        except OSError:
            continue
    return {"deleted_logs": deleted, "log_root": str(log_root)}


async def cleanup_old_runs() -> dict:
    """Delete old run records from Postgres."""
    now = datetime.now(timezone.utc)
    fail_cutoff = now - timedelta(days=RUN_RETENTION_DAYS_FAILED)
    ok_cutoff = now - timedelta(days=RUN_RETENTION_DAYS_SUCCESS)
    async with AsyncSessionLocal() as s:
        # Delete webhook_events referencing these runs first (FK)
        old_failed = (
            await s.execute(
                select(Run.id).where(Run.status == "failed", Run.created_at < fail_cutoff)
            )
        ).scalars().all()
        old_success = (
            await s.execute(
                select(Run.id).where(Run.status == "success", Run.created_at < ok_cutoff)
            )
        ).scalars().all()
        old_ids = list(old_failed) + list(old_success)
        if old_ids:
            # Detach webhook_events
            await s.execute(
                WebhookEvent.__table__.update()
                .where(WebhookEvent.run_id.in_(old_ids))
                .values(run_id=None)
            )
            await s.execute(delete(Run).where(Run.id.in_(old_ids)))
            await s.commit()
    return {"deleted_runs": len(old_ids)}


async def cleanup_orphaned_workspaces() -> dict:
    """Delete /tmp/surgeon-workspace/<id> dirs older than WORKSPACE_TTL_HOURS."""
    ws_root = Path(settings.workspace_root)
    if not ws_root.exists():
        return {"deleted": 0, "skipped": "workspace root missing"}
    cutoff = time.time() - WORKSPACE_TTL_HOURS * 3600
    deleted = 0
    for child in ws_root.iterdir():
        if not child.is_dir():
            continue
        try:
            if child.stat().st_mtime < cutoff:
                shutil.rmtree(child, ignore_errors=True)
                deleted += 1
        except OSError:
            continue
    return {"deleted_workspaces": deleted, "workspace_root": str(ws_root)}


async def run_all() -> dict:
    """Run all cleanup tasks and return a summary."""
    logs = await cleanup_old_logs()
    runs = await cleanup_old_runs()
    ws = await cleanup_orphaned_workspaces()
    summary = {**logs, **runs, **ws, "ran_at": datetime.now(timezone.utc).isoformat()}
    log.info("cleanup summary: %s", summary)
    return summary
