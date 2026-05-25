"""Target-repo workspace management. Shallow-clones, installs deps, cleans up."""
from __future__ import annotations

import asyncio
import shutil
import time
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


async def clone_target(
    repo_full_name: str,
    run_id: str,
    token: str,
    progress=None,
) -> Path:
    """Shallow-clone the target repo, install deps, create branch. Return path.

    `progress` is an optional async callable taking a string — used to publish
    prep-phase events to SSE so the dashboard doesn't go silent for 30+ sec
    during npm install.
    """
    async def _p(msg: str) -> None:
        if progress:
            await progress(msg)

    workspace_root = Path(settings.workspace_root) / run_id
    workspace_root.mkdir(parents=True, exist_ok=True)
    target_dir = workspace_root / "target"
    if target_dir.exists():
        shutil.rmtree(target_dir, ignore_errors=True)

    clone_url = f"https://x-access-token:{token}@github.com/{repo_full_name}.git"
    t0 = time.monotonic()
    rc, out = await _run(["git", "clone", "--depth=50", clone_url, str(target_dir)], timeout=120)
    if rc != 0:
        raise RuntimeError(f"git clone failed: {out[:300]}")
    await _p(f"[prep] ✓ cloned in {time.monotonic() - t0:.1f}s")

    await _run(["git", "config", "user.email", "repo-surgeon[bot]@users.noreply.github.com"], cwd=target_dir)
    await _run(["git", "config", "user.name", "repo-surgeon[bot]"], cwd=target_dir)

    await _run(["git", "checkout", "-b", f"surgeon/{run_id}"], cwd=target_dir)
    await _p(f"[prep] ✓ branch surgeon/{run_id} ready")

    await _install_deps(target_dir, progress=progress)

    return target_dir


async def _install_deps(target_dir: Path, progress=None) -> None:
    """Detect language and install dependencies. Best-effort, non-fatal."""
    async def _p(msg: str) -> None:
        if progress:
            await progress(msg)

    if (target_dir / "package.json").exists():
        await _p("[prep] ▶ npm install (Node/JS deps — first run is ~30-60s)...")
        t0 = time.monotonic()
        rc, _ = await _run(
            ["npm", "install", "--no-audit", "--no-fund", "--prefer-offline"],
            cwd=target_dir,
            timeout=300,
        )
        elapsed = time.monotonic() - t0
        await _p(f"[prep] {'✓' if rc == 0 else '⚠'} npm install ({elapsed:.1f}s)")

    if (target_dir / "requirements.txt").exists():
        await _p("[prep] ▶ pip install -r requirements.txt ...")
        t0 = time.monotonic()
        rc, _ = await _run(
            ["pip", "install", "--quiet", "--no-cache-dir", "-r", "requirements.txt"],
            cwd=target_dir,
            timeout=300,
        )
        await _p(f"[prep] {'✓' if rc == 0 else '⚠'} pip install ({time.monotonic() - t0:.1f}s)")
    elif (target_dir / "pyproject.toml").exists():
        await _p("[prep] ▶ pip install -e . ...")
        t0 = time.monotonic()
        rc, _ = await _run(
            ["pip", "install", "--quiet", "--no-cache-dir", "-e", "."],
            cwd=target_dir,
            timeout=300,
        )
        await _p(f"[prep] {'✓' if rc == 0 else '⚠'} pip install -e ({time.monotonic() - t0:.1f}s)")

    if (target_dir / "Gemfile").exists():
        await _p("[prep] ▶ bundle install ...")
        await _run(["bundle", "install", "--quiet"], cwd=target_dir, timeout=300)
    if (target_dir / "go.mod").exists():
        await _p("[prep] ▶ go mod download ...")
        await _run(["go", "mod", "download"], cwd=target_dir, timeout=300)
    if (target_dir / "Cargo.toml").exists():
        await _p("[prep] ▶ cargo fetch ...")
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
        await _run(["git", "pull", "--rebase", "--autostash"], cwd=agent_dir, timeout=30)
    return agent_dir
