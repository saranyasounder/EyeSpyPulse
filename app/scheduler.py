# app/scheduler.py
import logging
import sys

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger

from app.pipeline import run_pipeline

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("es-pulse-scheduler")


def job():
    log.info("Daily pipeline starting")
    try:
        run_pipeline()
        log.info("Daily pipeline finished")
    except Exception:
        # Log the failure and keep the scheduler alive so tomorrow's run
        # still happens. The API's is_stale flag makes a failure visible.
        log.exception("Daily pipeline failed")


if __name__ == "__main__":
    if "--now" in sys.argv:
        job()  # run once immediately, for testing
        sys.exit(0)

    scheduler = BlockingScheduler(timezone="America/Los_Angeles")
    scheduler.add_job(
        job,
        CronTrigger(hour=6, minute=0),
        id="daily_pipeline",
        max_instances=1,        # never overlap two runs
        coalesce=True,          # if several runs were missed, run once, not many
        misfire_grace_time=3600,  # still run if the machine woke up within the hour
    )
    log.info("Scheduler started. Pipeline runs daily at 06:00 Pacific.")
    scheduler.start()