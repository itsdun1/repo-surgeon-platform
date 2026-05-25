"""Apply memory edits from the dashboard. Each edit becomes a commit + push to the agent repo."""
from __future__ import annotations

import asyncio
from pathlib import Path

from app.config import settings


async def _run(cmd: list[str], cwd: Path) -> tuple[int, str]:
    proc = await asyncio.create_subprocess_exec(
        *cmd, cwd=str(cwd), stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT
    )
    stdout, _ = await proc.communicate()
    return proc.returncode or 0, (stdout or b"").decode(errors="ignore")


async def apply_memory_edit(file_path: str, new_content: str, message: str, edited_by: str) -> dict:
    """Write the new content to memory/<file_path>, commit, push. Returns commit info."""
    agent_dir = Path(settings.agent_repo_path).resolve()
    # Defense: prevent path traversal
    rel = Path(file_path).as_posix().lstrip("/")
    if ".." in rel.split("/"):
        raise ValueError("path traversal not allowed")
    target = agent_dir / "memory" / rel
    if not target.is_relative_to(agent_dir / "memory"):
        raise ValueError("file_path must be under memory/")

    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(new_content)

    # Commit
    rc, out = await _run(["git", "add", str(target.relative_to(agent_dir))], cwd=agent_dir)
    if rc != 0:
        return {"committed": False, "error": out[:300]}
    rc, out = await _run(
        ["git", "commit", "-m", message, "--author", f"{edited_by} <{edited_by}@local>"],
        cwd=agent_dir,
    )
    if rc != 0:
        return {"committed": False, "error": out[:300]}

    # Push (best-effort)
    rc, push_out = await _run(["git", "push", "origin", "HEAD"], cwd=agent_dir)
    return {
        "committed": True,
        "pushed": rc == 0,
        "push_output": push_out[:200] if rc != 0 else None,
        "file_path": str(target),
    }
