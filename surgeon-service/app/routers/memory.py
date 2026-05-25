"""Memory inspector + editor API."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.config import settings
from app.db.models import MemoryAudit, DEFAULT_TENANT
from app.db.session import AsyncSessionLocal
from app.services.memory_writer import apply_memory_edit

router = APIRouter(prefix="/api/memory", tags=["memory"])


@router.get("/tree")
async def memory_tree():
    """Return the memory/ tree structure."""
    agent_dir = Path(settings.agent_repo_path).resolve()
    mem = agent_dir / "memory"
    if not mem.exists():
        raise HTTPException(404, "memory dir not found")

    def walk(path: Path, base: Path) -> dict[str, Any]:
        node: dict[str, Any] = {
            "name": path.name,
            "type": "dir" if path.is_dir() else "file",
            "path": str(path.relative_to(base)),
        }
        if path.is_dir():
            node["children"] = sorted(
                [walk(p, base) for p in path.iterdir() if not p.name.startswith(".")],
                key=lambda x: (x["type"], x["name"]),
            )
        else:
            try:
                node["size"] = path.stat().st_size
            except Exception:
                node["size"] = 0
        return node

    return walk(mem, mem)


@router.get("/file")
async def get_memory_file(path: str):
    agent_dir = Path(settings.agent_repo_path).resolve()
    target = (agent_dir / "memory" / path).resolve()
    if not target.is_relative_to(agent_dir / "memory"):
        raise HTTPException(400, "path traversal not allowed")
    if not target.exists():
        raise HTTPException(404, "file not found")
    return {"path": path, "content": target.read_text(), "size": target.stat().st_size}


class MemoryEditRequest(BaseModel):
    path: str
    new_content: str
    message: str = "memory: human edit via dashboard"
    edited_by: str = "dashboard-user"


@router.patch("/file")
async def edit_memory_file(req: MemoryEditRequest):
    agent_dir = Path(settings.agent_repo_path).resolve()
    target = (agent_dir / "memory" / req.path).resolve()
    if not target.is_relative_to(agent_dir / "memory"):
        raise HTTPException(400, "path traversal not allowed")

    # Read before
    before = target.read_text() if target.exists() else None

    # Apply
    try:
        result = await apply_memory_edit(req.path, req.new_content, req.message, req.edited_by)
    except Exception as e:
        raise HTTPException(500, str(e)) from e

    # Audit row
    async with AsyncSessionLocal() as s:
        # extract repo from path: memory/repos/<repo>/...
        repo = ""
        parts = req.path.split("/")
        if parts[:1] == ["repos"] and len(parts) > 1:
            repo = parts[1]
        elif parts[:1] == ["org"]:
            repo = "org"
        audit = MemoryAudit(
            repo=repo,
            file_path=req.path,
            before_blob=before,
            after_blob=req.new_content,
            edited_by=req.edited_by,
        )
        s.add(audit)
        await s.commit()

    return result
