"""Background scheduler: periodic Nextcloud sync (and, later, reminder dispatch).

Runs inside the uvicorn process via APScheduler's asyncio scheduler. Each job
opens its own database session. Disabled during tests via SCHEDULER_ENABLED=false.
"""

from __future__ import annotations

import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.config import settings
from app.db import SessionLocal
from app.services.sync import sync_contacts

log = logging.getLogger("prism.scheduler")

_scheduler: AsyncIOScheduler | None = None


async def _run_contact_sync() -> None:
    async with SessionLocal() as session:
        try:
            await sync_contacts(session)
        except Exception:  # noqa: BLE001 - a failed sync must not kill the scheduler
            log.exception("Scheduled contact sync failed")


def start_scheduler() -> None:
    global _scheduler
    if _scheduler is not None:
        return
    if not (settings.scheduler_enabled and settings.nextcloud_configured):
        log.info("Scheduler not started (disabled or Nextcloud unconfigured)")
        return
    scheduler = AsyncIOScheduler()
    scheduler.add_job(
        _run_contact_sync,
        "interval",
        minutes=max(1, settings.sync_interval_minutes),
        id="contact_sync",
        coalesce=True,
        max_instances=1,
    )
    scheduler.start()
    _scheduler = scheduler
    log.info("Scheduler started (sync every %d min)", settings.sync_interval_minutes)


def shutdown_scheduler() -> None:
    global _scheduler
    if _scheduler is not None:
        _scheduler.shutdown(wait=False)
        _scheduler = None
