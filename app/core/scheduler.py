"""
Background scan scheduler using APScheduler.

Manages:
- Periodic check for due scheduled scans.
- Registration and removal of individual scan jobs.
- Reload of all active schedules on application startup.
- Graceful error handling and retry logic.
"""

import asyncio
import logging
from datetime import datetime, timezone
from uuid import UUID
from typing import Optional

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

from app.core.config import get_settings
from app.core.database import AsyncSessionLocal

logger = logging.getLogger("media_intel.scheduler")

# Module-level scheduler instance
scheduler: Optional[AsyncIOScheduler] = None


def get_scheduler() -> AsyncIOScheduler:
    """Get or create the global scheduler instance."""
    global scheduler
    if scheduler is None:
        scheduler = AsyncIOScheduler(
            job_defaults={
                "coalesce": True,
                "max_instances": 1,
                "misfire_grace_time": 300,
            }
        )
    return scheduler


async def execute_due_scans():
    """
    Check for and execute all due scheduled scans.

    Called periodically by the scheduler. Creates a fresh DB session
    for each check. Each due scan is executed in its own task.
    """
    from app.services.scan_service import ScanService
    from app.agents.orchestrator import ScanOrchestrator

    logger.info("Scheduler: checking for due scans...")

    async with AsyncSessionLocal() as db:
        try:
            scan_service = ScanService(db)
            due_scans = await scan_service.get_due_scheduled_scans()

            if not due_scans:
                logger.debug("Scheduler: no scans due")
                return

            logger.info(f"Scheduler: found {len(due_scans)} due scans")

            for scan in due_scans:
                try:
                    logger.info(
                        f"Scheduler: executing scan {scan.id} "
                        f"target={scan.target.display_name if scan.target else scan.target_id}",
                        extra={"action": "scheduled_scan_start", "scan_id": str(scan.id)},
                    )

                    # Execute in a fresh session to isolate transactions
                    async with AsyncSessionLocal() as scan_db:
                        orchestrator = ScanOrchestrator(scan_db)
                        await orchestrator.execute_scan(
                            scan_id=scan.id,
                            target_id=scan.target_id,
                            user_id=scan.user_id,
                        )

                    logger.info(
                        f"Scheduler: scan {scan.id} completed",
                        extra={"action": "scheduled_scan_complete", "scan_id": str(scan.id)},
                    )

                except Exception as e:
                    logger.exception(
                        f"Scheduler: scan {scan.id} failed — {e}",
                        extra={"action": "scheduled_scan_fail", "scan_id": str(scan.id)},
                    )
                    # Failure is already recorded in execute_scan → fail_scan
                    # Continue to next scan

        except Exception as e:
            logger.exception(f"Scheduler: error checking due scans — {e}")


async def reload_schedules():
    """
    Reload all active scheduled scans from the database on startup.

    Ensures that schedules persist across application restarts.
    """
    from app.services.scan_service import ScanService

    async with AsyncSessionLocal() as db:
        try:
            scan_service = ScanService(db)
            active_schedules = await scan_service.get_all_active_schedules()

            logger.info(
                f"Scheduler: reloaded {len(active_schedules)} active schedules from database",
                extra={"action": "scheduler_reload"},
            )

            for scan in active_schedules:
                if scan.next_run_at and scan.next_run_at <= datetime.now(timezone.utc):
                    logger.info(
                        f"Scheduler: scan {scan.id} is overdue "
                        f"(was due at {scan.next_run_at}), will run on next check",
                    )

        except Exception as e:
            logger.exception(f"Scheduler: error reloading schedules — {e}")


async def remove_scheduled_job(scan_id: str):
    """
    Remove a specific scan job from the scheduler.

    Note: Since we use a periodic check pattern (not individual jobs per scan),
    this is a no-op. The scan's is_schedule_active flag in the DB controls
    whether it gets picked up by the periodic check.

    Args:
        scan_id: UUID string of the scan to remove.
    """
    logger.info(
        f"Scheduler: scan {scan_id} marked inactive — will not run on next check",
        extra={"action": "scheduler_remove", "scan_id": scan_id},
    )


def start_scheduler():
    """
    Start the background scheduler.

    Adds a periodic job that checks for due scans every 60 seconds.
    """
    sched = get_scheduler()

    if not sched.running:
        # Check for due scans every 60 seconds
        sched.add_job(
            execute_due_scans,
            trigger=IntervalTrigger(seconds=60),
            id="check_due_scans",
            name="Check and execute due scheduled scans",
            replace_existing=True,
        )
        sched.start()
        logger.info(
            "Scheduler started — checking for due scans every 60 seconds",
            extra={"action": "scheduler_start"},
        )


def stop_scheduler():
    """Stop the background scheduler gracefully."""
    global scheduler
    if scheduler and scheduler.running:
        scheduler.shutdown(wait=False)
        logger.info("Scheduler stopped", extra={"action": "scheduler_stop"})
