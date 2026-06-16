"""Background scheduler: periodic Nextcloud sync (and, later, reminder dispatch).

Runs inside the uvicorn process via APScheduler's asyncio scheduler. Each job
opens its own database session. Disabled during tests via SCHEDULER_ENABLED=false.
"""

from __future__ import annotations

import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy import select

from app.config import settings
from app.db import SessionLocal
from app.models import User
from app.services.nextcloud_accounts import user_has_personal_nextcloud
from app.services.sync import sync_contacts

log = logging.getLogger("prism.scheduler")

_scheduler: AsyncIOScheduler | None = None


async def _run_contact_sync() -> None:
    """Sync each user who has configured their own Nextcloud."""
    async with SessionLocal() as session:
        users = (await session.scalars(select(User).where(User.is_active.is_(True)))).all()
        for user in users:
            if not user_has_personal_nextcloud(user):
                continue
            try:
                await sync_contacts(session, user)
            except Exception:  # noqa: BLE001 - one user's failure must not stop the rest
                log.exception("Scheduled contact sync failed for user %d", user.id)


def start_scheduler() -> None:
    global _scheduler
    if _scheduler is not None:
        return
    if not settings.scheduler_enabled:
        log.info("Scheduler not started (disabled)")
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
