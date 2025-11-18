from fastapi import FastAPI
from sqlmodel import Session
from prometheus_fastapi_instrumentator import Instrumentator
from sqlalchemy import inspect, text

from . import config
from .database import create_db_and_tables, engine
from .scheduler import scheduler, schedule_database_backups, schedule_system_jobs, initialize_metrics, configure_scheduler
from .routers import databases, backups, packages, system
from .logger import setup_logging, get_logger

setup_logging()
logger = get_logger(__name__)

app = FastAPI()
Instrumentator().instrument(app).expose(app)

import yaml

def run_db_migrations():
    """
    Checks for and applies necessary database schema migrations.
    This is a simple migration helper for a small project without Alembic.
    """
    logger.info("Checking for database migrations...")
    try:
        with engine.connect() as connection:
            inspector = inspect(engine)

            # --- Migration for 'trigger_mode' in 'backup' table ---
            backup_columns = [c['name'] for c in inspector.get_columns('backup')]
            if 'trigger_mode' not in backup_columns:
                logger.info("Migration: Adding 'trigger_mode' column to 'backup' table.")
                with connection.begin():
                    connection.execute(text("ALTER TABLE backup ADD COLUMN trigger_mode VARCHAR(255) DEFAULT 'scheduled'"))
                    connection.execute(text("CREATE INDEX ix_backup_trigger_mode ON backup (trigger_mode)"))

            # --- Migration for 'trigger_mode' in 'package' table ---
            package_columns = [c['name'] for c in inspector.get_columns('package')]
            if 'trigger_mode' not in package_columns:
                logger.info("Migration: Adding 'trigger_mode' column to 'package' table.")
                with connection.begin():
                    connection.execute(text("ALTER TABLE package ADD COLUMN trigger_mode VARCHAR(255) DEFAULT 'scheduled'"))
                    connection.execute(text("CREATE INDEX ix_package_trigger_mode ON package (trigger_mode)"))
        logger.info("Database migration check complete.")
    except Exception as e:
        logger.error(f"An error occurred during database migration: {e}", exc_info=True)
        # Depending on the severity, you might want to exit the application
        raise e

@app.on_event("startup")
def startup_event():
    create_db_and_tables()
    run_db_migrations()

    global_conf = {}
    package_conf = {}
    try:
        with open("config.yaml", "r") as f:
            config_data = yaml.safe_load(f)
            global_conf = config_data.get("global", {})
            package_conf = config_data.get("package-conf", {})
    except FileNotFoundError:
        logger.info("No config.yaml found, skipping configuration.")
    except yaml.YAMLError as e:
        logger.error(f"Error parsing config.yaml: {e}")

    with Session(engine) as session:
        config.load_and_sync_databases(session)

    max_workers = global_conf.get("max_parallel_jobs", 10)
    configure_scheduler(max_workers=max_workers)

    scheduler.start()
    schedule_database_backups()
    schedule_system_jobs(package_conf)
    initialize_metrics()

@app.on_event("shutdown")
def shutdown_event():
    scheduler.shutdown()

app.include_router(databases.router, prefix="/databases", tags=["databases"])
app.include_router(backups.router, prefix="/backups", tags=["backups"])
app.include_router(packages.router, prefix="/packages", tags=["packages"])
app.include_router(system.router, prefix="/system", tags=["system"])
