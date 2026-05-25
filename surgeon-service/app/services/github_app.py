"""GitHub App JWT + installation token minting.

Caches installation tokens in Redis until 5 minutes before expiry.
"""
from __future__ import annotations

import json
import time
from datetime import datetime, timezone

import httpx
import jwt

from app.config import settings


def app_jwt() -> str:
    """Sign a short-lived JWT as the GitHub App."""
    private_key = settings.github_app_private_key
    if not private_key or not settings.github_app_id:
        raise RuntimeError("GitHub App credentials not configured")
    now = int(time.time())
    payload = {
        "iat": now - 60,  # back-date for clock skew
        "exp": now + 9 * 60,
        "iss": settings.github_app_id,
    }
    return jwt.encode(payload, private_key, algorithm="RS256")


async def mint_installation_token(installation_id: int, redis_client=None) -> tuple[str, datetime]:
    """Mint or fetch a cached installation token. Returns (token, expires_at)."""
    cache_key = f"installation_token:{installation_id}"
    if redis_client is not None:
        cached_raw = await redis_client.get(cache_key)
        if cached_raw:
            cached = json.loads(cached_raw)
            return cached["token"], datetime.fromisoformat(cached["expires_at"])

    token = app_jwt()
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post(
            f"https://api.github.com/app/installations/{installation_id}/access_tokens",
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
            },
        )
        resp.raise_for_status()
        data = resp.json()
    installation_token = data["token"]
    expires_at = datetime.fromisoformat(data["expires_at"].replace("Z", "+00:00"))

    if redis_client is not None:
        ttl_s = max(60, int((expires_at - datetime.now(timezone.utc)).total_seconds()) - 300)
        await redis_client.set(
            cache_key,
            json.dumps({"token": installation_token, "expires_at": expires_at.isoformat()}),
            ex=ttl_s,
        )
    return installation_token, expires_at
