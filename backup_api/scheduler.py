from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from typing import Dict
from datetime import datetime, timedelta
import os
import logging

from .models import Database, Backup
from .backup_manager import run_backup

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

scheduler = BackgroundScheduler()

def trigger_scheduled_backup(db: Database, backups: Dict[str, Backup]):
    """
    Wrapper function to create a backup record before running the backup.
    """
    logger.info(f"Triggering scheduled backup for database: {db.name}")
    new_backup = Backup(database_id=db.id, type="scheduled")
    backups[new_backup.id] = new_backup
    run_backup(new_backup.id, db, backups)

def schedule_database_backups(databases: Dict[str, Database], backups: Dict[str, Backup]):
    """
    Schedules backup jobs for all databases that have a cron schedule defined.
    """
    for db_id, db in databases.items():
        if db.schedule:
            job_id = f"backup_{db_id}"
            # Use a wrapper to create a backup object on-the-fly
            scheduler.add_job(
                trigger_scheduled_backup,
                trigger=CronTrigger.from_crontab(db.schedule),
                args=[db, backups],
                id=job_id,
                name=f"Backup for {db.name}",
                replace_existing=True,
            )
            logger.info(f"Scheduled backup for '{db.name}' with schedule: '{db.schedule}'")
        else:
            # If the schedule is removed, remove the job
            job_id = f"backup_{db_id}"
            if scheduler.get_job(job_id):
                scheduler.remove_job(job_id)
                logger.info(f"Removed backup schedule for '{db.name}'.")

def schedule_retention_policy(databases: Dict[str, Database], backups: Dict[str, Backup]):
    """
    Schedules a daily job to enforce retention policies.
    """
    job_id = "retention_policy_job"
    if not scheduler.get_job(job_id):
        scheduler.add_job(
            enforce_retention,
            trigger="cron",
            hour=1, # Run once a day at 1 AM
            args=[databases, backups],
            id=job_id,
            name="Enforce Retention Policies",
            replace_existing=True,
        )
        logger.info("Scheduled daily retention policy job.")

def enforce_retention(databases: Dict[str, Database], backups: Dict[str, Backup]):
    """
    Deletes old backups based on the retention policy of each database.
    """
    logger.info("Running retention policy enforcement...")
    now = datetime.utcnow()

    for backup_id, backup in list(backups.items()):
        db = databases.get(backup.database_id)

        if db and db.retention_days is not None and backup.status == "completed":
            retention_delta = timedelta(days=db.retention_days)
            if now - backup.finished_at > retention_delta:
                try:
                    if os.path.exists(backup.storage_path):
                        os.remove(backup.storage_path)
                    del backups[backup_id]
                    logger.info(f"Deleted old backup '{backup_id}' for database '{db.name}'.")
                except Exception as e:
                    logger.error(f"Error deleting backup file for '{backup_id}': {e}")
