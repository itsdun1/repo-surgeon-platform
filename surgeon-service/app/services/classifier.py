"""Classify incoming GitHub webhook payloads into agent modes."""
from __future__ import annotations

from typing import Any

# Mapping of mode -> (event_type, action, label_filter)
# Returns the first matching mode or None to skip.

SURGEON_LABEL_PREFIX = "surgeon:"


def classify(event_type: str, payload: dict[str, Any]) -> dict[str, Any] | None:
    """Return {mode, repo, issue_number?, model?} or None to skip."""
    action = payload.get("action")
    repo = payload.get("repository", {}).get("full_name", "")
    if not repo:
        return None

    if event_type == "issues" and action == "labeled":
        label = payload.get("label", {}).get("name", "")
        if label.startswith(SURGEON_LABEL_PREFIX):
            mode = label.removeprefix(SURGEON_LABEL_PREFIX)
            return {
                "mode": f"issue:{mode}",
                "repo": repo,
                "issue_number": payload["issue"]["number"],
                "installation_id": payload.get("installation", {}).get("id"),
            }

    if event_type == "issue_comment" and action == "created":
        body = payload.get("comment", {}).get("body", "")
        if body.startswith("/surgeon "):
            return {
                "mode": "manual:" + body.split()[1] if len(body.split()) > 1 else "manual:fix",
                "repo": repo,
                "issue_number": payload.get("issue", {}).get("number"),
                "installation_id": payload.get("installation", {}).get("id"),
            }

    if event_type == "pull_request" and action == "opened":
        # Passive: post a review comment, not edit code
        return {
            "mode": "pr-review",
            "repo": repo,
            "pr_number": payload["pull_request"]["number"],
            "installation_id": payload.get("installation", {}).get("id"),
        }

    # Ignore: push (we use cron for scans), other actions
    return None
