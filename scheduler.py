"""
SaKgaZé / Weathernext Automated Pipeline Scheduler

Runs the three production pipelines every 6 hours:
  1. sakgaze.src.pipeline     (satellite sargassum detection)
  2. weathernext.src.pipeline (marine weather & cyclone tracking)
  3. drift.src.engine         (coupled drift & risk scoring)

Usage:
    PYTHONPATH= .venv/bin/python scheduler.py
"""
import logging
import sys
from datetime import datetime, timezone

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger

from sakgaze.src.pipeline import run_pipeline as run_sakgaze
from weathernext.src.pipeline import run_pipeline as run_weathernext
from drift.src.engine import run_engine as run_drift

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger("caribbean_scheduler")


def run_all_pipelines():
    """Execute the full platform pipeline chain."""
    logger.info("=== Scheduler tick: running Caribbean platform pipelines ===")
    started = datetime.now(timezone.utc)
    try:
        run_sakgaze()
        logger.info("SaKgaZé pipeline completed")
    except Exception as exc:
        logger.error(f"SaKgaZé pipeline failed: {exc}", exc_info=True)

    try:
        run_weathernext()
        logger.info("Weathernext pipeline completed")
    except Exception as exc:
        logger.error(f"Weathernext pipeline failed: {exc}", exc_info=True)

    try:
        run_drift()
        logger.info("Drift engine completed")
    except Exception as exc:
        logger.error(f"Drift engine failed: {exc}", exc_info=True)

    elapsed = (datetime.now(timezone.utc) - started).total_seconds()
    logger.info(f"=== Scheduler tick finished in {elapsed:.1f}s ===")


def main():
    scheduler = BackgroundScheduler()
    scheduler.add_job(
        run_all_pipelines,
        trigger=IntervalTrigger(hours=6),
        id="caribbean_pipeline_tick",
        name="SaKgaZé / Weathernext 6-hour pipeline",
        replace_existing=True,
        next_run_time=datetime.now(timezone.utc),
    )
    scheduler.start()
    logger.info("Scheduler started; pipelines will run every 6 hours. Press Ctrl+C to exit.")
    try:
        while True:
            import time
            time.sleep(60)
    except (KeyboardInterrupt, SystemExit):
        scheduler.shutdown()
        logger.info("Scheduler stopped")
        sys.exit(0)


if __name__ == "__main__":
    main()
