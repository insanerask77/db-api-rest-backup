import os
import subprocess
import hashlib
import time
from datetime import datetime
from sqlmodel import Session
from .models import Backup, Database
from .database import engine
from .metrics import BACKUPS_TOTAL, BACKUP_DURATION_SECONDS, BACKUP_SIZE_BYTES

STORAGE_DIR = "backup_api/storage"

def run_backup(backup_id: str, db_id: str):
    start_time = time.time()
    with Session(engine) as session:
        backup = session.get(Backup, backup_id)
        db = session.get(Database, db_id)

        if not backup or not db:
            return

        file_path = os.path.join(STORAGE_DIR, f"{backup.id}.bak")
        status = "failed"

        try:
            if not os.path.exists(STORAGE_DIR):
                os.makedirs(STORAGE_DIR)

            if db.engine == "postgres":
                env = os.environ.copy()
                env["PGPASSWORD"] = db.password
                cmd = [
                    "pg_dump", "-h", db.host, "-p", str(db.port), "-U", db.username,
                    "-d", db.database_name, "-f", file_path, "--format=c"
                ]
                result = subprocess.run(cmd, env=env, capture_output=True, text=True)
            elif db.engine == "mongodb":
                uri = f"mongodb://{db.username}:{db.password}@{db.host}:{db.port}/{db.database_name}?authSource=admin"
                cmd = ["mongodump", f"--uri={uri}", f"--archive={file_path}", "--gzip"]
                result = subprocess.run(cmd, capture_output=True, text=True)
            else:
                raise ValueError(f"Unsupported database engine: {db.engine}")

            if result.returncode != 0:
                raise RuntimeError(f"Backup failed: {result.stderr}")

            with open(file_path, "rb") as f:
                file_content = f.read()
                backup.size_bytes = len(file_content)
                backup.checksum = hashlib.sha256(file_content).hexdigest()
                BACKUP_SIZE_BYTES.labels(database_name=db.name).set(backup.size_bytes)

            backup.storage_path = file_path
            status = "completed"
            backup.log = result.stdout or result.stderr

        except Exception as e:
            backup.log = str(e)

        finally:
            duration = time.time() - start_time
            backup.finished_at = datetime.utcnow()
            backup.status = status

            session.add(backup)
            session.commit()

            BACKUPS_TOTAL.labels(database_name=db.name, status=status).inc()
            BACKUP_DURATION_SECONDS.labels(database_name=db.name).observe(duration)
