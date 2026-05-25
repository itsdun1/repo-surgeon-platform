"""FastAPI app — webhooks, runs, SSE, memory, evals, manual triggers."""
from __future__ import annotations

import asyncio
import contextlib
import logging
from contextlib import asynccontextmanager

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers import admin, evals, manual, memory, repos, runs, sse, webhooks
from app.services import cleanup
from app.workers.consumer import supervisor

log = logging.getLogger("surgeon")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Start the worker supervisor
    worker_task = asyncio.create_task(supervisor.start())

    # Schedule daily cleanup at 03:00 UTC
    scheduler = AsyncIOScheduler(timezone="UTC")
    scheduler.add_job(cleanup.run_all, CronTrigger(hour=3, minute=0), id="daily-cleanup", replace_existing=True)
    # Also run once on startup to immediately tidy old workspaces
    scheduler.add_job(cleanup.run_all, id="startup-cleanup", replace_existing=True)
    scheduler.start()
    log.info("scheduler started; daily cleanup at 03:00 UTC")

    try:
        yield
    finally:
        scheduler.shutdown(wait=False)
        await supervisor.stop()
        worker_task.cancel()
        with contextlib.suppress(asyncio.CancelledError, Exception):
            await worker_task


app = FastAPI(
    title="surgeon-service",
    description="Webhook dispatcher for Repo Surgeon. Receives GitHub events, classifies, queues, spawns the gitagent CLI.",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(webhooks.router)
app.include_router(runs.router)
app.include_router(sse.router)
app.include_router(memory.router)
app.include_router(repos.router)
app.include_router(manual.router)
app.include_router(evals.router)
app.include_router(admin.router)


@app.get("/health")
async def health():
    return {"status": "ok", "service": "surgeon-service"}


@app.get("/")
async def root():
    return {
        "service": "surgeon-service",
        "version": "0.1.0",
        "endpoints": [
            "POST /webhooks/github",
            "GET /api/repos",
            "GET /api/agents/runs",
            "GET /api/runs/{id}",
            "GET /sse/runs/{id}",
            "GET /api/memory/tree",
            "GET /api/memory/file?path=...",
            "PATCH /api/memory/file",
            "POST /api/manual-trigger",
            "GET /api/evals",
        ],
    }
