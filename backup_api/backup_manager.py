import time
import os
import hashlib
from datetime import datetime
from typing import Dict
from backup_api.models import Backup

STORAGE_DIR = "backup_api/storage"

def run_backup(backup_id: str, backups: Dict[str, Backup]):
    """
    Simulates a backup process.
    """
    backup = backups.get(backup_id)
    if not backup:
        return

    # Simulate backup time
    time.sleep(5)

    # Create dummy backup file
    if not os.path.exists(STORAGE_DIR):
        os.makedirs(STORAGE_DIR)

    file_path = os.path.join(STORAGE_DIR, f"{backup.id}.bak")
    file_content = f"Backup for database {backup.database_id} at {datetime.utcnow()}"

    with open(file_path, "w") as f:
        f.write(file_content)

    # Calculate size and checksum
    size_bytes = os.path.getsize(file_path)
    checksum = hashlib.sha256(file_content.encode("utf-8")).hexdigest()

    # Update backup status
    backup.status = "completed"
    backup.finished_at = datetime.utcnow()
    backup.size_bytes = size_bytes
    backup.storage_path = file_path
    backup.checksum = checksum
