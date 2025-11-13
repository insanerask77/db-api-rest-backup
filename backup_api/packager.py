import os
import logging
import datetime
import zipfile
import tarfile
import hashlib
from sqlmodel import Session, select

from .models import Database, Backup, Package
from .backup_manager import run_backup
from .metrics import PACKAGE_LAST_STATUS, PACKAGES_TOTAL, PACKAGES_SIZE_BYTES

logger = logging.getLogger(__name__)

def create_package(session: Session, compression: str = "zip"):
    """
    Finds all databases marked for packaging, gathers their latest backups,
    and compresses them into a single package file.
    """
    PACKAGE_LAST_STATUS.set(0)
    package_dir = "data/packages"
    os.makedirs(package_dir, exist_ok=True)

    dbs_to_package = session.exec(select(Database).where(Database.package == True)).all()
    if not dbs_to_package:
        logger.info("No databases are marked for packaging. Skipping.")
        return

    backup_files = []
    for db in dbs_to_package:
        latest_backup = session.exec(
            select(Backup)
            .where(Backup.database_id == db.id)
            .where(Backup.status == "completed")
            .order_by(Backup.finished_at.desc())
        ).first()

        if not latest_backup:
            logger.info(f"No backup found for '{db.name}'. Triggering a new one.")
            try:
                backup_id = run_backup(db.id, session)
                latest_backup = session.get(Backup, backup_id)
                if not latest_backup or latest_backup.status != "completed":
                    raise Exception("Newly created backup failed.")
            except Exception as e:
                logger.error(f"Failed to create a backup for '{db.name}'. Halting package creation. Error: {e}")
                raise

        backup_files.append(latest_backup.storage_path)

    timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    package_name = f"packaged_database_{timestamp}"

    if compression == "zip":
        package_path = os.path.join(package_dir, f"{package_name}.zip")
        with zipfile.ZipFile(package_path, 'w') as zipf:
            for file in backup_files:
                zipf.write(file, os.path.basename(file))
    elif compression == "tar.gz":
        package_path = os.path.join(package_dir, f"{package_name}.tar.gz")
        with tarfile.open(package_path, 'w:gz') as tar:
            for file in backup_files:
                tar.add(file, arcname=os.path.basename(file))
    else:
        raise ValueError(f"Unsupported compression type: {compression}")

    size_bytes = os.path.getsize(package_path)
    with open(package_path, "rb") as f:
        checksum = hashlib.md5(f.read()).hexdigest()

    new_package = Package(
        storage_path=package_path,
        size_bytes=size_bytes,
        checksum=checksum
    )
    session.add(new_package)
    session.commit()

    PACKAGE_LAST_STATUS.set(1)
    PACKAGES_TOTAL.inc()
    PACKAGES_SIZE_BYTES.inc(size_bytes)

    logger.info(f"Successfully created package: {package_path}")
