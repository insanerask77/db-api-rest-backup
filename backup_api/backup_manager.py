import os
import subprocess
import hashlib
from datetime import datetime
from sqlmodel import Session, select
from .models import Backup, Database
from .database import engine

STORAGE_DIR = "backup_api/storage"

def run_backup(backup_id: str, db_id: str):
    """
    Runs a real backup process using pg_dump or mongodump.
    """
    with Session(engine) as session:
        backup = session.get(Backup, backup_id)
        db = session.get(Database, db_id)

        if not backup or not db:
            return

        file_path = os.path.join(STORAGE_DIR, f"{backup.id}.bak")

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

            backup.storage_path = file_path
            backup.status = "completed"
            backup.log = result.stdout or result.stderr

        except Exception as e:
            backup.status = "failed"
            backup.log = str(e)

        finally:
            backup.finished_at = datetime.utcnow()
            session.add(backup)
            session.commit()
