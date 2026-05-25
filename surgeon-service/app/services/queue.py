"""Redis-backed per-repo job queue."""
from __future__ import annotations

import json
from typing import Any

import redis.asyncio as redis

from app.config import settings

_client: redis.Redis | None = None


def get_redis() -> redis.Redis:
    global _client
    if _client is None:
        _client = redis.from_url(settings.redis_url, decode_responses=True)
    return _client


async def enqueue(repo_id: str, job: dict[str, Any]) -> None:
    r = get_redis()
    await r.lpush(f"queue:repo:{repo_id}", json.dumps(job))


async def dequeue(repo_id: str, timeout: int = 10) -> dict[str, Any] | None:
    r = get_redis()
    result = await r.brpop([f"queue:repo:{repo_id}"], timeout=timeout)
    if not result:
        return None
    _, raw = result
    return json.loads(raw)


async def all_active_repos() -> list[str]:
    r = get_redis()
    keys = []
    async for k in r.scan_iter("queue:repo:*"):
        keys.append(k.removeprefix("queue:repo:"))
    return keys


async def dedupe_event(delivery_id: str) -> bool:
    """Return True if this is a new event, False if duplicate."""
    r = get_redis()
    return bool(await r.set(f"webhook:{delivery_id}", "1", nx=True, ex=86400))


async def publish_log(run_id: str, line: str) -> None:
    r = get_redis()
    await r.publish(f"sse:{run_id}", line)


async def acquire_repo_lock(repo_id: str, timeout: int = 1800) -> bool:
    r = get_redis()
    return bool(await r.set(f"lock:repo:{repo_id}", "1", nx=True, ex=timeout))


async def release_repo_lock(repo_id: str) -> None:
    r = get_redis()
    await r.delete(f"lock:repo:{repo_id}")
