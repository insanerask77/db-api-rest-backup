from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from datetime import datetime, timedelta
import os
import logging
import psutil
from sqlmodel import Session, select
from typing import Optional

from .models import Database, Backup, Package
from .backup_manager import run_backup
from .packager import create_package
from .database import engine
from .metrics import (
    RETENTION_POLICY_RUNS_TOTAL, RETENTION_FILES_DELETED_TOTAL,
    BACKUP_LAST_STATUS
)
from .storage import get_storage_provider
from .config import load_config

from apscheduler.executors.pool import ThreadPoolExecutor

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# This will be configured in main.py
scheduler = BackgroundScheduler()
config = load_config()
storage = get_storage_provider(config)

def configure_scheduler(max_workers=10):
    executors = {
        'default': ThreadPoolExecutor(max_workers)
    }
    scheduler.configure(executors=executors)

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
            RETENTION_POLICY_RUNS_TOTAL.labels(database_name=db.name).inc()
            files_deleted_count = 0
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
                    if backup.storage_path:
                        storage.delete(backup.storage_path)
                        files_deleted_count += 1
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
                        if backup.storage_path:
                            storage.delete(backup.storage_path)
                            files_deleted_count += 1
                        session.delete(backup)
                        logger.info(f"Deleted old backup '{backup.id}' for '{db.name}' (count policy).")

            session.commit()
            if files_deleted_count > 0:
                RETENTION_FILES_DELETED_TOTAL.labels(database_name=db.name).inc(files_deleted_count)

def schedule_system_jobs(package_conf=None):
    scheduler.add_job(enforce_retention, "cron", hour=1, id="retention_policy_job", name="Enforce Retention Policies", replace_existing=True)

    if package_conf and package_conf.get('schedule'):
        schedule_package_creation(package_conf)

    logger.info("Scheduled system jobs (retention, metrics, and packaging).")

def schedule_package_creation(package_conf):
    job_id = "package_creation_job"

    def job_wrapper():
        with Session(engine) as session:
            create_package(session, package_conf.get('compression', 'zip'))
            enforce_package_retention(session, package_conf)

    scheduler.add_job(
        job_wrapper,
        trigger=CronTrigger.from_crontab(package_conf['schedule'], timezone=os.getenv("TZ", "UTC")),
        id=job_id,
        name="Create Backup Package",
        replace_existing=True,
    )
    logger.info(f"Scheduled package creation with schedule: '{package_conf['schedule']}'")

def enforce_package_retention(session: Session, package_conf):
    logger.info("Running package retention policy.")

    retention_days = package_conf.get('retention_days')
    max_packages = package_conf.get('max_packages')

    if retention_days is not None:
        cutoff_date = datetime.utcnow() - timedelta(days=retention_days)
        packages_to_delete = session.exec(
            select(Package).where(Package.created_at < cutoff_date)
        ).all()
        for pkg in packages_to_delete:
            storage.delete(pkg.storage_path)
            session.delete(pkg)
            logger.info(f"Deleted old package '{pkg.id}' (time policy).")

    if max_packages is not None:
        all_packages = session.exec(select(Package).order_by(Package.created_at.desc())).all()
        if len(all_packages) > max_packages:
            packages_to_delete = all_packages[max_packages:]
            for pkg in packages_to_delete:
                storage.delete(pkg.storage_path)
                session.delete(pkg)
                logger.info(f"Deleted old package '{pkg.id}' (count policy).")

    session.commit()

def initialize_metrics():
    with Session(engine) as session:
        databases = session.exec(select(Database)).all()
        for db in databases:
            BACKUP_LAST_STATUS.labels(database_name=db.name).set(-1)
    logger.info("Initialized metrics for all databases.")
