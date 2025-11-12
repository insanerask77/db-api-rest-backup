from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from datetime import datetime, timedelta
import os
import logging
import psutil
from sqlmodel import Session, select
from typing import Optional

from .models import Database, Backup
from .backup_manager import run_backup, STORAGE_DIR
from .database import engine
from .metrics import DISK_SPACE_AVAILABLE_BYTES

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
scheduler = BackgroundScheduler()

def update_disk_space_metric():
    if os.path.exists(STORAGE_DIR):
        disk_usage = psutil.disk_usage(STORAGE_DIR)
        DISK_SPACE_AVAILABLE_BYTES.set(disk_usage.free)

def trigger_scheduled_backup(db_id: str):
    with Session(engine) as session:
        db = session.get(Database, db_id)
        if db:
            logger.info(f"Triggering scheduled backup for database: {db.name}")
            new_backup = Backup(database_id=db.id, type="scheduled")
            session.add(new_backup)
            session.commit()
            session.refresh(new_backup)
            run_backup(new_backup.id, db.id)

def schedule_database_backups():
    with Session(engine) as session:
        databases = session.exec(select(Database)).all()
        for db in databases:
            job_id = f"backup_{db.id}"
            if db.schedule:
                scheduler.add_job(
                    trigger_scheduled_backup,
                    trigger=CronTrigger.from_crontab(db.schedule, timezone=os.getenv("TZ", "UTC")),
                    args=[db.id],
                    id=job_id,
                    name=f"Backup for {db.name}",
                    replace_existing=True,
                )
                logger.info(f"Scheduled backup for '{db.name}' with schedule: '{db.schedule}'")
            elif scheduler.get_job(job_id):
                scheduler.remove_job(job_id)
                logger.info(f"Removed backup schedule for '{db.name}'.")

def enforce_retention(database_id: Optional[str] = None):
    with Session(engine) as session:
        logger.info(f"Running retention policy for database_id: {database_id or 'all'}")

        dbs_to_check = []
        if database_id:
            db = session.get(Database, database_id)
            if db:
                dbs_to_check.append(db)
        else:
            dbs_to_check = session.exec(select(Database)).all()

        now = datetime.utcnow()
        for db in dbs_to_check:
            # Time-based retention
            if db.retention_days is not None:
                cutoff_date = now - timedelta(days=db.retention_days)
                backups_to_delete = session.exec(
                    select(Backup).where(
                        Backup.database_id == db.id,
                        Backup.status == "completed",
                        Backup.finished_at < cutoff_date
                    )
                ).all()
                for backup in backups_to_delete:
                    if backup.storage_path and os.path.exists(backup.storage_path):
                        os.remove(backup.storage_path)
                    session.delete(backup)
                    logger.info(f"Deleted old backup '{backup.id}' for '{db.name}' (time policy).")

            # Count-based retention
            if db.max_backups is not None:
                all_backups = session.exec(
                    select(Backup).where(
                        Backup.database_id == db.id,
                        Backup.status == "completed"
                    ).order_by(Backup.finished_at.desc())
                ).all()

                if len(all_backups) > db.max_backups:
                    backups_to_delete = all_backups[db.max_backups:]
                    for backup in backups_to_delete:
                        if backup.storage_path and os.path.exists(backup.storage_path):
                            os.remove(backup.storage_path)
                        session.delete(backup)
                        logger.info(f"Deleted old backup '{backup.id}' for '{db.name}' (count policy).")

            session.commit()

def schedule_system_jobs():
    scheduler.add_job(enforce_retention, "cron", hour=1, id="retention_policy_job", name="Enforce Retention Policies", replace_existing=True)
    scheduler.add_job(update_disk_space_metric, "interval", minutes=5, id="disk_space_metric_job", name="Update Disk Space Metric", replace_existing=True)
    logger.info("Scheduled system jobs (retention and metrics).")
