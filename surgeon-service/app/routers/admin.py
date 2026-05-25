"""Admin / utility endpoints (manual cleanup trigger)."""
from __future__ import annotations

from fastapi import APIRouter

from app.services import cleanup

router = APIRouter(prefix="/api/admin", tags=["admin"])


@router.post("/cleanup")
async def trigger_cleanup():
    """Manually trigger the cleanup job. Returns a summary."""
    return await cleanup.run_all()
