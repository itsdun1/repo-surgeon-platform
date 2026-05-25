"""Spawn the gitagent CLI subprocess, stream stdout, parse outputs."""
from __future__ import annotations

import asyncio
import json
import os
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.config import settings
from app.services import queue, workspace

PR_URL_RE = re.compile(r"https://github\.com/[^/\s]+/[^/\s]+/pull/(\d+)")
COST_RE = re.compile(r"cost[:\s]+\$?([0-9.]+)", re.IGNORECASE)


def build_prompt(job: dict[str, Any]) -> str:
    """Build a prompt for the agent given the job classification."""
    mode = job["mode"]
    repo = job["repo"]
    if mode.startswith("issue:"):
        kind = mode.split(":", 1)[1]
        issue_no = job.get("issue_number")
        title = job.get("issue_title", "(no title captured)")
        body = job.get("issue_body", "")
        labels = ", ".join(job.get("issue_labels", []) or [])
        url = job.get("issue_url", "")
        return f"""You are repo-surgeon, an autonomous coding agent. A new issue has been labeled `surgeon:{kind}`.

## Issue context (pre-fetched — do NOT call read-issue or github-api to fetch this)
- Repo: {repo}
- Issue #: {issue_no}
- URL: {url}
- Labels: {labels}
- Title: {title}

### Issue body
{body or '(empty)'}

## Workspace
- The target repo is already cloned at: $TARGET_DIR
- You are NOT in the agent repo workspace; do all code edits inside $TARGET_DIR
- A branch `surgeon/{job['run_id']}` has been created for you
- Dependencies are pre-installed (npm install / pip install already ran in the clone step)
- GITHUB_TOKEN is set in env; use it for git push and any GitHub API calls

## Your job
Execute the `issue-to-pr` workflow:
1. Classify the issue using `skills/classify-issue/SKILL.md` (bug | feature | refactor | wont-fix | needs-clarification). The labels above are authoritative — `surgeon:{kind}` means kind={kind}.
2. For a `bug`, follow `skills/fix-from-issue/SKILL.md`:
   - Locate the buggy code in $TARGET_DIR (use built-in `read`, `cli` grep/find)
   - Write a FAILING regression test FIRST (RULE 14)
   - Implement the smallest fix
   - Run tests via `cli` (e.g. `cd $TARGET_DIR && npm test`) — must pass before PR
3. Honor RULES.md. Specifically:
   - RULE 13: never open a PR if tests fail or can't run
   - RULE 11: one concern per PR
   - RULE 17: cite the issue in the PR body
4. Open the PR with the GitHub CLI: `cd $TARGET_DIR && gh pr create --title "[surgeon:{kind}] <imperative summary>" --body "<body>" --label "surgeon:{kind}" --label "needs-review"`
   - `gh` is authenticated via GITHUB_TOKEN env
   - PR body should have sections: ## What changed / ## Why / ## How I tested / ## Risk / ## Sources
5. After opening, capture the PR URL from `gh`'s output and print it to stdout on its own line so the dispatcher can capture it.

Do NOT try to recursively invoke `gitagent` — use the built-in `cli`, `read`, `write`, `edit` tools directly.
"""
    if mode == "manual:scan":
        return (
            f"Execute the `refactor-workflow` against {repo}. Pick ONE smell from the backlog, "
            f"propose a minimal refactor, validate with tests, open a single PR."
        )
    if mode == "pr-review":
        pr_no = job.get("pr_number")
        return (
            f"A new PR was opened on {repo} (#{pr_no}). Read it (read-only). Post a brief comment "
            f"with observations. Do NOT modify code. Do NOT open another PR."
        )
    if mode == "cron:refactor":
        return (
            f"Nightly refactor scan for {repo}. Execute the `refactor-workflow`. "
            f"Honor RULE 9 (max 1 refactor PR per 24h)."
        )
    # manual fallback
    return f"Process {repo} per mode `{mode}`. Use your judgment."


async def run_agent(job: dict[str, Any], run_id: str, db_callback, model: str | None = None) -> dict[str, Any]:
    """Spawn gitagent CLI, stream output, capture results.

    db_callback: async function(status: str, **kwargs) — updates the runs row.
    """
    repo = job["repo"]
    token = job["github_token"]
    installation_id = job.get("installation_id")

    # 1. Acquire per-repo lock (serializes runs on the same repo)
    repo_lock_key = repo.replace("/", "__")
    locked = await queue.acquire_repo_lock(repo_lock_key, timeout=settings.max_duration_s_per_run + 60)
    if not locked:
        return {"status": "skipped", "reason": "another run is already in progress for this repo"}

    log_path = Path(settings.log_root).expanduser().resolve() / f"{run_id}.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_file = log_path.open("w")

    async def progress(msg: str) -> None:
        """Publish a prep-phase event to SSE and persist to log file."""
        line = msg if msg.endswith("\n") else msg + "\n"
        log_file.write(line)
        log_file.flush()
        await queue.publish_log(run_id, msg)

    try:
        await db_callback(status="running", started_at=datetime.now(timezone.utc), log_path=str(log_path))

        await progress(f"[prep] received job mode={job.get('mode')} repo={repo} issue={job.get('issue_number')}")

        # 2. Ensure agent repo is at latest
        await progress("[prep] ▶ pulling latest agent repo (./repo-surgeon)...")
        agent_dir = await workspace.ensure_agent_repo_latest()
        await progress(f"[prep] ✓ agent repo at {agent_dir}")

        # 3. Clone target + install deps
        await progress(f"[prep] ▶ cloning target repo {repo} (shallow, depth=50)...")
        try:
            target_dir = await workspace.clone_target(repo, run_id, token, progress=progress)
        except Exception as e:
            await progress(f"[prep] ✗ clone failed: {e}")
            await db_callback(
                status="failed",
                finished_at=datetime.now(timezone.utc),
                error=f"clone failed: {e}",
            )
            log_file.close()
            return {"status": "failed", "reason": "clone failed", "error": str(e)}
        await progress(f"[prep] ✓ workspace ready at {target_dir}")

        # 4. Build prompt
        prompt = build_prompt(job)

        # 5. Spawn gitagent CLI
        chosen_model = model or settings.default_model
        cmd = [
            shutil.which("gitagent") or "gitagent",
            "--dir",
            str(agent_dir),
            "--prompt",
            prompt,
            "--model",
            chosen_model,
        ]
        env = {
            **os.environ,
            "TARGET_DIR": str(target_dir),
            "TARGET_REPO": repo,
            "GITHUB_TOKEN": token,
            "AGENT_REPO_PATH": str(agent_dir),
            "ANTHROPIC_API_KEY": settings.anthropic_api_key,
            "OPENAI_API_KEY": settings.openai_api_key,
        }

        await progress(f"[prep] ▶ spawning gitagent (model={chosen_model})...")
        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                env=env,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
            )
        except FileNotFoundError:
            await progress("[prep] ✗ gitagent CLI not installed")
            await db_callback(
                status="failed",
                finished_at=datetime.now(timezone.utc),
                error="gitagent CLI not installed",
            )
            log_file.close()
            await workspace.cleanup_workspace(run_id)
            return {"status": "failed", "reason": "gitagent CLI not installed"}
        await progress(f"[prep] ✓ agent spawned (pid={proc.pid})\n")

        # 6. Stream stdout to log file + Redis pubsub
        log_buf: list[str] = []
        assert proc.stdout is not None
        async for raw_line in proc.stdout:
            line = raw_line.decode(errors="ignore")
            log_file.write(line)
            log_file.flush()
            log_buf.append(line)
            await queue.publish_log(run_id, line.rstrip("\n"))

        rc = await asyncio.wait_for(proc.wait(), timeout=60)
        full_log = "".join(log_buf)

        # 7. Parse PR URL and cost from log
        pr_url = None
        pr_number = None
        m = PR_URL_RE.search(full_log)
        if m:
            pr_url = m.group(0)
            pr_number = int(m.group(1))

        cost = None
        m2 = COST_RE.search(full_log)
        if m2:
            try:
                cost = float(m2.group(1))
            except ValueError:
                pass

        status = "success" if rc == 0 else "failed"
        await db_callback(
            status=status,
            finished_at=datetime.now(timezone.utc),
            exit_code=rc,
            pr_url=pr_url,
            pr_number=pr_number,
            cost_usd=cost,
        )
        await queue.publish_log(run_id, json.dumps({"event": "complete", "status": status, "pr_url": pr_url}))

        return {
            "status": status,
            "pr_url": pr_url,
            "pr_number": pr_number,
            "exit_code": rc,
            "log_path": str(log_path),
        }

    finally:
        try:
            log_file.close()
        except Exception:
            pass
        await workspace.cleanup_workspace(run_id)
        await queue.release_repo_lock(repo_lock_key)
