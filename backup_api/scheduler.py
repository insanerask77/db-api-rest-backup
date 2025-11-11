from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from datetime import datetime, timedelta
import os
import logging
from sqlmodel import Session, select
from .models import Database, Backup
from .backup_manager import run_backup
from .database import engine

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
scheduler = BackgroundScheduler()

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
                    trigger=CronTrigger.from_crontab(db.schedule),
                    args=[db.id],
                    id=job_id,
                    name=f"Backup for {db.name}",
                    replace_existing=True,
                )
                logger.info(f"Scheduled backup for '{db.name}' with schedule: '{db.schedule}'")
            elif scheduler.get_job(job_id):
                scheduler.remove_job(job_id)
                logger.info(f"Removed backup schedule for '{db.name}'.")

def enforce_retention():
    with Session(engine) as session:
        logger.info("Running retention policy enforcement...")
        now = datetime.utcnow()
        databases = {db.id: db for db in session.exec(select(Database)).all()}

        backups_to_delete = session.exec(select(Backup).where(Backup.status == "completed")).all()

        for backup in backups_to_delete:
            db = databases.get(backup.database_id)
            if db and db.retention_days is not None:
                retention_delta = timedelta(days=db.retention_days)
                if now - backup.finished_at > retention_delta:
                    try:
                        if backup.storage_path and os.path.exists(backup.storage_path):
                            os.remove(backup.storage_path)
                        session.delete(backup)
                        logger.info(f"Deleted old backup '{backup.id}' for database '{db.name}'.")
                    except Exception as e:
                        logger.error(f"Error deleting backup file for '{backup.id}': {e}")
        session.commit()

def schedule_retention_policy():
    job_id = "retention_policy_job"
    if not scheduler.get_job(job_id):
        scheduler.add_job(
            enforce_retention,
            trigger="cron",
            hour=1,
            id=job_id,
            name="Enforce Retention Policies",
            replace_existing=True,
        )
        logger.info("Scheduled daily retention policy job.")
