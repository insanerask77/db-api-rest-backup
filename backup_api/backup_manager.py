import os
import subprocess
import hashlib
import time
import gzip
import tempfile
from datetime import datetime
from sqlmodel import Session
from .models import Backup, Database
from .database import engine
from .metrics import (
    BACKUPS_TOTAL, BACKUP_DURATION_SECONDS, BACKUP_SIZE_BYTES, BACKUPS_DELETED_TOTAL,
    BACKUP_LAST_STATUS, BACKUP_LAST_SUCCESSFUL_SCHEDULED_TIMESTAMP_SECONDS,
    BACKUP_TRANSFER_SPEED_BYTES_PER_SECOND, BACKUP_LAST_INTEGRITY_STATUS
)
from .storage import get_storage_provider
from .config import load_config

config = load_config()
storage = get_storage_provider(config)

def run_backup(backup_id: str, db_id: str):
    start_time = time.time()
    with Session(engine) as session:
        backup = session.get(Backup, backup_id)
        db = session.get(Database, db_id)

        if not backup or not db:
            return

        timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
        file_extension = ".sql" if db.engine == "postgres" else ".archive"
        if db.compression == "gzip":
            file_extension += ".gz"

        filename = f"{db.engine}_{db.database_name}_{timestamp}{file_extension}"
        # The storage path will be relative, not absolute
        storage_path = os.path.join("backups", filename)
        status = "failed"

        with tempfile.NamedTemporaryFile(delete=False) as tmp_file:
            tmp_path = tmp_file.name

        try:
            if db.engine == "postgres":
                env = os.environ.copy()
                env["PGPASSWORD"] = db.password
                cmd = [
                    "pg_dump", "-h", db.host, "-p", str(db.port), "-U", db.username,
                    "-d", db.database_name, "--format=c"
                ]

                result = subprocess.run(cmd, env=env, capture_output=True)

                if result.returncode == 0:
                    if db.compression == "gzip":
                        with gzip.open(tmp_path, "wb") as f:
                            f.write(result.stdout)
                    else:
                        with open(tmp_path, "wb") as f:
                            f.write(result.stdout)
                else:
                     raise RuntimeError(f"Backup failed: {result.stderr.decode('utf-8')}")

            elif db.engine == "mongodb":
                uri = f"mongodb://{db.username}:{db.password}@{db.host}:{db.port}/{db.database_name}?authSource=admin"
                cmd = ["mongodump", f"--uri={uri}", f"--archive={tmp_path}"]
                if db.compression == "gzip":
                    cmd.append("--gzip")

                result = subprocess.run(cmd, capture_output=True, text=True)
            else:
                raise ValueError(f"Unsupported database engine: {db.engine}")

            if result.returncode != 0:
                raise RuntimeError(f"Backup failed: {result.stderr}")

            storage.save(source_path=tmp_path, destination_path=storage_path)

            with open(tmp_path, "rb") as f:
                file_content = f.read()
                backup.size_bytes = len(file_content)
                backup.checksum = hashlib.md5(file_content).hexdigest()
                BACKUP_SIZE_BYTES.labels(database_name=db.name).set(backup.size_bytes)

            backup.storage_path = storage_path
            status = "completed"
            backup.log = result.stdout or result.stderr

        except Exception as e:
            backup.log = str(e)

        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)

            duration = time.time() - start_time
            backup.finished_at = datetime.utcnow()
            backup.status = status

            session.add(backup)
            session.commit()

            BACKUPS_TOTAL.labels(database_name=db.name, status=status).inc()
            BACKUP_DURATION_SECONDS.labels(database_name=db.name).observe(duration)
            BACKUP_LAST_STATUS.labels(database_name=db.name).set(1 if status == "completed" else 0)

            if status == "completed":
                if backup.checksum:
                    BACKUP_LAST_INTEGRITY_STATUS.labels(database_name=db.name).set(1)
                else:
                    BACKUP_LAST_INTEGRITY_STATUS.labels(database_name=db.name).set(0)

                if backup.size_bytes and duration > 0:
                    speed = backup.size_bytes / duration
                    BACKUP_TRANSFER_SPEED_BYTES_PER_SECOND.labels(database_name=db.name).set(speed)

                if backup.type == "scheduled":
                    BACKUP_LAST_SUCCESSFUL_SCHEDULED_TIMESTAMP_SECONDS.labels(database_name=db.name).set(backup.finished_at.timestamp())

                from .scheduler import enforce_retention
                enforce_retention(db.id)
            else:
                BACKUP_LAST_INTEGRITY_STATUS.labels(database_name=db.name).set(0)


def create_and_run_backup_sync(db: Database, session: Session) -> Backup:
    """
    Creates, runs, and returns a backup synchronously.
    """
    new_backup = Backup(database_id=db.id, type="on-demand")
    session.add(new_backup)
    session.commit()
    session.refresh(new_backup)

    run_backup(new_backup.id, db.id)

    # Re-fetch the backup to get its final status and details
    session.refresh(new_backup)
    return new_backup


def delete_backup(backup_id: str) -> bool:
    with Session(engine) as session:
        backup = session.get(Backup, backup_id)
        if not backup:
            return False

        db = session.get(Database, backup.database_id)
        if not db:
            return False

        if backup.storage_path:
            storage.delete(backup.storage_path)

        session.delete(backup)
        session.commit()

        BACKUPS_DELETED_TOTAL.labels(database_name=db.name).inc()
        return True
