"""SSE log streaming endpoint."""
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


async def _historical_lines(log_path: str | None):
    """Yield lines already in the log file."""
    if not log_path:
        return
    p = Path(log_path)
    if not p.exists():
        return
    for line in p.read_text(errors="ignore").splitlines():
        yield line


async def _stream(run_id: str, request: Request):
    redis_client = get_redis()
    pubsub = redis_client.pubsub()
    channel = f"sse:{run_id}"
    await pubsub.subscribe(channel)

    # Send historical lines first (so reloads work)
    async with AsyncSessionLocal() as s:
        r = (await s.execute(select(Run).where(Run.id == run_id))).scalar_one_or_none()
    if r and r.log_path:
        async for line in _historical_lines(r.log_path):
            yield f"data: {json.dumps({'kind': 'historical', 'line': line})}\n\n"

    try:
        while True:
            if await request.is_disconnected():
                break
            msg = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
            if msg is None:
                yield ": keepalive\n\n"
                await asyncio.sleep(0.5)
                continue
            data = msg.get("data")
            if isinstance(data, bytes):
                data = data.decode()
            yield f"data: {json.dumps({'kind': 'live', 'line': data})}\n\n"
    finally:
        await pubsub.unsubscribe(channel)
        await pubsub.close()


@router.get("/runs/{run_id}")
async def stream_run(run_id: str, request: Request):
    return StreamingResponse(_stream(run_id, request), media_type="text/event-stream")
