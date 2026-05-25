"""SSE log streaming endpoint.

Two modes:
- LIVE: run is queued or running. Stream historical → live pubsub → keepalive.
- TERMINAL: run is success/failed/cancelled. Stream historical → stream_end → close.

The TERMINAL mode is critical: without it, the client EventSource will sit on a
keepalive loop forever and eventually be marked as "disconnected" by the browser.
"""
from __future__ import annotations

import asyncio
import json
from pathlib import Path

from fastapi import APIRouter, Request
from sqlalchemy import select
from starlette.responses import StreamingResponse

from app.db.models import Run
from app.db.session import AsyncSessionLocal
from app.services.queue import get_redis

router = APIRouter(prefix="/sse", tags=["sse"])

TERMINAL_STATUSES = {"success", "failed", "cancelled"}


def _format_event(kind: str, **payload) -> str:
    """Format a single SSE message (one event)."""
    body = {"kind": kind, **payload}
    return f"data: {json.dumps(body)}\n\n"


async def _yield_log_file(log_path: str | None):
    """Yield historical events from the log file (one event per line)."""
    if not log_path:
        return
    p = Path(log_path)
    if not p.exists():
        return
    try:
        content = p.read_text(errors="ignore")
    except OSError:
        return
    for line in content.splitlines():
        yield _format_event("historical", line=line)


async def _stream(run_id: str, request: Request):
    # Look up the run record to know its terminal state + log path
    async with AsyncSessionLocal() as s:
        r = (await s.execute(select(Run).where(Run.id == run_id))).scalar_one_or_none()

    if not r:
        yield _format_event("error", message=f"run {run_id} not found")
        yield _format_event("stream_end", reason="not_found")
        return

    # 1. Always replay historical content first
    async for evt in _yield_log_file(r.log_path):
        yield evt

    # 2a. Terminal run → emit final marker and close gracefully
    if r.status in TERMINAL_STATUSES:
        yield _format_event(
            "stream_end",
            reason="run_complete",
            status=r.status,
            pr_url=r.pr_url,
            exit_code=r.exit_code,
        )
        return

    # 2b. Live run → subscribe to pubsub + keepalives
    redis_client = get_redis()
    pubsub = redis_client.pubsub()
    channel = f"sse:{run_id}"
    await pubsub.subscribe(channel)
    try:
        idle_ticks = 0
        while True:
            if await request.is_disconnected():
                break

            # Periodically re-check the run status — if it just hit terminal, stop.
            if idle_ticks % 10 == 0:
                async with AsyncSessionLocal() as s2:
                    fresh = (
                        await s2.execute(select(Run.status, Run.pr_url, Run.exit_code).where(Run.id == run_id))
                    ).first()
                if fresh and fresh.status in TERMINAL_STATUSES:
                    yield _format_event(
                        "stream_end",
                        reason="run_complete",
                        status=fresh.status,
                        pr_url=fresh.pr_url,
                        exit_code=fresh.exit_code,
                    )
                    break

            msg = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
            if msg is None:
                yield ": keepalive\n\n"
                idle_ticks += 1
                continue

            data = msg.get("data")
            if isinstance(data, bytes):
                data = data.decode(errors="ignore")
            yield _format_event("live", line=data)
            idle_ticks = 0
    finally:
        await pubsub.unsubscribe(channel)
        await pubsub.close()


@router.get("/runs/{run_id}")
async def stream_run(run_id: str, request: Request):
    return StreamingResponse(
        _stream(run_id, request),
        media_type="text/event-stream",
        headers={
            # Prevent intermediate proxies (NGINX, Next.js dev/prod, smee, etc.) from buffering
            "Cache-Control": "no-cache, no-transform",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )
