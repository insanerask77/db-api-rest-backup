import os
import logging
import datetime
import zipfile
import tarfile
import hashlib
import tempfile
import shutil
from sqlmodel import Session, select

from .models import Database, Backup, Package
from .backup_manager import create_and_run_backup_sync
from .metrics import PACKAGE_LAST_STATUS, PACKAGES_TOTAL, PACKAGES_SIZE_BYTES
from .storage import get_storage_provider
from .logger import get_logger

logger = get_logger(__name__)


def create_package(session: Session, compression: str = "zip", trigger_mode: str = "scheduled"):
    """
    Finds all databases marked for packaging, gathers their latest backups,
    and compresses them into a single package file.
    """
    storage = get_storage_provider()
    PACKAGE_LAST_STATUS.set(0)

    tmp_dir = tempfile.mkdtemp()

    try:
        dbs_to_package = session.exec(select(Database).where(Database.package == True)).all()
        if not dbs_to_package:
            logger.info("No databases are marked for packaging. Skipping.")
            return

        backup_files_to_pack = []
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
                    # Propagate the trigger mode to on-the-fly backups
                    latest_backup = create_and_run_backup_sync(db, session, trigger_mode=trigger_mode)
                    if not latest_backup or latest_backup.status != "completed":
                        raise Exception("Newly created backup failed.")
                except Exception as e:
                    logger.error(f"Failed to create a backup for '{db.name}'. Halting package creation. Error: {e}")
                    raise

            local_backup_path = os.path.join(tmp_dir, os.path.basename(latest_backup.storage_path))
            storage.download_file(latest_backup.storage_path, local_backup_path)
            backup_files_to_pack.append(local_backup_path)

        timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        manual_suffix = "_manual" if trigger_mode == "manual" else ""
        package_name = f"paquete-backups_{timestamp}{manual_suffix}"

        with tempfile.NamedTemporaryFile(delete=False) as tmp_package_file:
            package_tmp_path = tmp_package_file.name

        if compression == "zip":
            ext = ".zip"
            with zipfile.ZipFile(package_tmp_path, 'w') as zipf:
                for file in backup_files_to_pack:
                    zipf.write(file, os.path.basename(file))
        elif compression == "tar.gz":
            ext = ".tar.gz"
            with tarfile.open(package_tmp_path, 'w:gz') as tar:
                for file in backup_files_to_pack:
                    tar.add(file, arcname=os.path.basename(file))
        else:
            raise ValueError(f"Unsupported compression type: {compression}")

        package_storage_path = os.path.join("packages", f"{package_name}{ext}")

        size_bytes = os.path.getsize(package_tmp_path)
        with open(package_tmp_path, "rb") as f:
            checksum = hashlib.md5(f.read()).hexdigest()

        storage.save(source_path=package_tmp_path, destination_path=package_storage_path)
        if os.path.exists(package_tmp_path):
            os.remove(package_tmp_path)

        new_package = Package(
            storage_path=package_storage_path,
            size_bytes=size_bytes,
            checksum=checksum,
            trigger_mode=trigger_mode
        )
        session.add(new_package)
        session.commit()

        PACKAGE_LAST_STATUS.set(1)
        PACKAGES_TOTAL.inc()
        PACKAGES_SIZE_BYTES.inc(size_bytes)

        logger.info(f"Successfully created package: {package_storage_path}")

    finally:
        shutil.rmtree(tmp_dir)
