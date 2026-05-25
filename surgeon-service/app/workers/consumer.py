"""Asyncio worker: drains per-repo queues, runs the agent, updates DB."""
from __future__ import annotations

import asyncio
import contextlib
from datetime import datetime, timezone

from sqlalchemy import update

from app.db.models import Run
from app.db.session import AsyncSessionLocal
from app.services import queue, runner


async def update_run(run_id: str, **fields):
    async with AsyncSessionLocal() as s:
        await s.execute(update(Run).where(Run.id == run_id).values(**fields))
        await s.commit()


async def process_one(job: dict) -> None:
    run_id = job["run_id"]

    async def cb(**kwargs):
        await update_run(run_id, **kwargs)

    await runner.run_agent(job, run_id, db_callback=cb, model=job.get("model"))


async def consume_repo(repo_id: str) -> None:
    while True:
        try:
            job = await queue.dequeue(repo_id, timeout=10)
            if job is None:
                # No work — return so the supervisor can clean us up
                return
            await process_one(job)
        except asyncio.CancelledError:
            raise
        except Exception as e:  # noqa: BLE001
            print(f"worker error for repo {repo_id}: {e}")
            await asyncio.sleep(1)


class WorkerSupervisor:
    """Spawns one consumer task per active repo. Polls every 5s for new repos."""

    def __init__(self):
        self.tasks: dict[str, asyncio.Task] = {}
        self._running = False

    async def start(self):
        self._running = True
        while self._running:
            try:
                repos = await queue.all_active_repos()
                for repo_id in repos:
                    if repo_id not in self.tasks or self.tasks[repo_id].done():
                        self.tasks[repo_id] = asyncio.create_task(consume_repo(repo_id))
                # Clean up finished tasks
                for repo_id, task in list(self.tasks.items()):
                    if task.done():
                        self.tasks.pop(repo_id, None)
            except Exception as e:  # noqa: BLE001
                print(f"supervisor error: {e}")
            await asyncio.sleep(5)

    async def stop(self):
        self._running = False
        for t in self.tasks.values():
            t.cancel()
        for t in self.tasks.values():
            with contextlib.suppress(Exception):
                await t


supervisor = WorkerSupervisor()
