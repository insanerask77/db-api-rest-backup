import asyncio
import logging
import os
from datetime import datetime
from sqlmodel import Session
from .models import Database, Restore
from .storage import StorageProvider

logger = logging.getLogger(__name__)

async def run_restore(
    db_session: Session,
    restore_id: str,
    db: Database,
    backup_file_path: str,
):
    """
    Runs the restore process for a given database using a specific backup file.
    """
    restore = db_session.get(Restore, restore_id)
    if not restore:
        logger.error(f"Restore record with id {restore_id} not found.")
        return

    try:
        if db.engine == "postgres":
            await _run_postgres_restore(restore, db, backup_file_path)
        elif db.engine == "mongodb":
            await _run_mongodb_restore(restore, db, backup_file_path)
        else:
            raise NotImplementedError(f"Restore for engine '{db.engine}' is not implemented.")

        restore.status = "completed"
        logger.info(f"Restore {restore.id} completed successfully for database {db.name}.")

    except Exception as e:
        logger.error(f"Restore {restore.id} failed for database {db.name}: {e}")
        restore.status = "failed"
        restore.error_summary = str(e)

    finally:
        restore.finished_at = datetime.utcnow()
        db_session.add(restore)
        db_session.commit()
        db_session.refresh(restore)


async def _run_postgres_restore(restore: Restore, db: Database, backup_file_path: str):
    """
    Restores a PostgreSQL database.
    """
    # Note: pg_restore requires password to be passed via PGPASSWORD env var.
    env = {
        "PGPASSWORD": db.password,
        **os.environ
    }

    cmd = [
        "pg_restore",
        "--host", db.host,
        "--port", str(db.port),
        "--username", db.username,
        "--dbname", db.database_name,
        "--clean",
        "--if-exists",
        "--verbose",
        backup_file_path,
    ]

    process = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        env=env,
    )

    stdout, stderr = await process.communicate()

    restore.log = stderr.decode()
    if process.returncode != 0:
        raise Exception(f"pg_restore failed with exit code {process.returncode}:\n{stderr.decode()}")


async def _run_mongodb_restore(restore: Restore, db: Database, backup_file_path: str):
    """
    Restores a MongoDB database.
    """
    cmd = [
        "mongorestore",
        f"--host={db.host}",
        f"--port={db.port}",
        f"--username={db.username}",
        f"--password={db.password}",
        f"--db={db.database_name}",
        "--drop",
        "--gzip",
        f"--archive={backup_file_path}",
    ]

    process = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )

    stdout, stderr = await process.communicate()

    restore.log = stderr.decode()
    if process.returncode != 0:
        raise Exception(f"mongorestore failed with exit code {process.returncode}:\n{stderr.decode()}")
