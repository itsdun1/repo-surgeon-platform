"""Target-repo workspace management. Shallow-clones, cleans up."""
from __future__ import annotations

import asyncio
import shutil
from pathlib import Path

from app.config import settings


async def _run(cmd: list[str], cwd: Path | None = None, timeout: int = 60) -> tuple[int, str]:
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        cwd=str(cwd) if cwd else None,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
    )
    try:
        stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=timeout)
    except asyncio.TimeoutError:
        proc.kill()
        return -1, "timeout"
    return proc.returncode or 0, (stdout or b"").decode(errors="ignore")


async def clone_target(repo_full_name: str, run_id: str, token: str) -> Path:
    """Shallow-clone the target repo into a per-run workspace, return the path."""
    workspace_root = Path(settings.workspace_root) / run_id
    workspace_root.mkdir(parents=True, exist_ok=True)
    target_dir = workspace_root / "target"
    if target_dir.exists():
        shutil.rmtree(target_dir, ignore_errors=True)

    clone_url = f"https://x-access-token:{token}@github.com/{repo_full_name}.git"
    rc, out = await _run(["git", "clone", "--depth=50", clone_url, str(target_dir)], timeout=120)
    if rc != 0:
        raise RuntimeError(f"git clone failed: {out[:300]}")

    # Configure git identity for commits the agent makes
    await _run(["git", "config", "user.email", "repo-surgeon[bot]@users.noreply.github.com"], cwd=target_dir)
    await _run(["git", "config", "user.name", "repo-surgeon[bot]"], cwd=target_dir)

    # Create the session branch
    await _run(["git", "checkout", "-b", f"surgeon/{run_id}"], cwd=target_dir)

    # Pre-install dependencies so the agent's `npm test` / `pytest` can run.
    # Best-effort: ignore failures here so the agent can still attempt to run
    # tests later (it'll surface a clearer error if deps are still missing).
    await _install_deps(target_dir)

    return target_dir


async def _install_deps(target_dir: Path) -> None:
    """Detect language and install dependencies. Best-effort, non-fatal."""
    if (target_dir / "package.json").exists():
        await _run(
            ["npm", "install", "--no-audit", "--no-fund", "--prefer-offline"],
            cwd=target_dir,
            timeout=300,
        )
    if (target_dir / "requirements.txt").exists():
        await _run(
            ["pip", "install", "--quiet", "--no-cache-dir", "-r", "requirements.txt"],
            cwd=target_dir,
            timeout=300,
        )
    elif (target_dir / "pyproject.toml").exists():
        await _run(
            ["pip", "install", "--quiet", "--no-cache-dir", "-e", "."],
            cwd=target_dir,
            timeout=300,
        )
    if (target_dir / "Gemfile").exists():
        await _run(["bundle", "install", "--quiet"], cwd=target_dir, timeout=300)
    if (target_dir / "go.mod").exists():
        await _run(["go", "mod", "download"], cwd=target_dir, timeout=300)
    if (target_dir / "Cargo.toml").exists():
        await _run(["cargo", "fetch", "--quiet"], cwd=target_dir, timeout=300)


async def cleanup_workspace(run_id: str) -> None:
    """Remove the per-run workspace directory."""
    workspace_root = Path(settings.workspace_root) / run_id
    if workspace_root.exists():
        shutil.rmtree(workspace_root, ignore_errors=True)


async def ensure_agent_repo_latest() -> Path:
    """git pull --rebase on the local agent repo."""
    agent_dir = settings.resolved_agent_repo_path()
    if not agent_dir.exists():
        if not settings.agent_repo_remote:
            raise RuntimeError(f"Agent repo not at {agent_dir} and no remote configured")
        agent_dir.parent.mkdir(parents=True, exist_ok=True)
        rc, out = await _run(["git", "clone", settings.agent_repo_remote, str(agent_dir)], timeout=120)
        if rc != 0:
            raise RuntimeError(f"agent repo clone failed: {out[:300]}")
    else:
        # Try to pull; ignore failures (e.g., no remote configured locally)
        await _run(["git", "pull", "--rebase", "--autostash"], cwd=agent_dir, timeout=30)
    return agent_dir
