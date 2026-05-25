"""HMAC-SHA256 webhook signature verification."""
from __future__ import annotations

import hashlib
import hmac

from app.config import settings


def verify_github_signature(body: bytes, signature_header: str | None) -> bool:
    """Verify the X-Hub-Signature-256 header against the request body.

    Supports rotation: accepts either the current or previous secret.
    """
    if not signature_header or not signature_header.startswith("sha256="):
        return False
    sig = signature_header.removeprefix("sha256=")
    for secret in (settings.github_webhook_secret, settings.github_webhook_secret_previous):
        if not secret:
            continue
        digest = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
        if hmac.compare_digest(digest, sig):
            return True
    return False
