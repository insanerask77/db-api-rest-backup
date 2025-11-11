import os
import subprocess
import hashlib
from datetime import datetime
from typing import Dict
from .models import Backup, Database

STORAGE_DIR = "backup_api/storage"

def run_backup(backup_id: str, db: Database, backups: Dict[str, Backup]):
    """
    Runs a real backup process using pg_dump or mongodump.
    """
    backup = backups.get(backup_id)
    if not backup:
        return

    file_path = os.path.join(STORAGE_DIR, f"{backup.id}.bak")

    try:
        if not os.path.exists(STORAGE_DIR):
            os.makedirs(STORAGE_DIR)

        if db.engine == "postgres":
            # Set environment variables for pg_dump
            env = os.environ.copy()
            env["PGPASSWORD"] = db.password

            # Construct pg_dump command
            cmd = [
                "pg_dump",
                "-h", db.host,
                "-p", str(db.port),
                "-U", db.username,
                "-d", db.database_name,
                "-f", file_path,
                "--format=c"
            ]

            result = subprocess.run(cmd, env=env, capture_output=True, text=True)

        elif db.engine == "mongodb":
            # Construct mongodump command
            uri = f"mongodb://{db.username}:{db.password}@{db.host}:{db.port}/{db.database_name}?authSource=admin"
            cmd = [
                "mongodump",
                f"--uri={uri}",
                f"--archive={file_path}",
                "--gzip"
            ]

            result = subprocess.run(cmd, capture_output=True, text=True)

        else:
            raise ValueError(f"Unsupported database engine: {db.engine}")

        if result.returncode != 0:
            raise RuntimeError(f"Backup failed: {result.stderr}")

        # Calculate size and checksum
        with open(file_path, "rb") as f:
            file_content = f.read()
            size_bytes = len(file_content)
            checksum = hashlib.sha256(file_content).hexdigest()

        # Update backup status to completed
        backup.status = "completed"
        backup.finished_at = datetime.utcnow()
        backup.size_bytes = size_bytes
        backup.storage_path = file_path
        backup.checksum = checksum
        backup.log = result.stdout or result.stderr

    except Exception as e:
        # Update backup status to failed
        backup.status = "failed"
        backup.finished_at = datetime.utcnow()
        backup.log = str(e)
