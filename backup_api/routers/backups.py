from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlmodel import Session, select
from typing import List

from ..models import Database, Backup
from ..schemas import BackupCreate, BackupInfo, BackupList, BackupDetail
from ..database import get_session
from .. import backup_manager
from ..storage import get_storage_provider
from ..config import load_config
from ..logger import get_logger

logger = get_logger(__name__)
router = APIRouter()
config = load_config()
storage = get_storage_provider(config)

@router.post("", response_model=BackupInfo)
def create_backup(backup_req: BackupCreate, background_tasks: BackgroundTasks, session: Session = Depends(get_session)):
    logger.info(f"Received request to create backup for database_id: {backup_req.database_id}")
    database = session.get(Database, backup_req.database_id)
    if not database:
        logger.warning(f"Database not found for id: {backup_req.database_id}")
        raise HTTPException(status_code=404, detail="Database not found")

    logger.debug(f"Creating '{database.engine}' backup entry for database '{database.name}'")
    new_backup = Backup(database_id=database.id, type=database.engine)
    session.add(new_backup)
    session.commit()
    session.refresh(new_backup)

    background_tasks.add_task(backup_manager.run_backup, new_backup.id, database.id)

    return new_backup

@router.get("", response_model=List[BackupList])
def list_backups(session: Session = Depends(get_session)):
    logger.info("Listing all backups.")
    backups = session.exec(select(Backup)).all()
    logger.debug(f"Found {len(backups)} total backups.")
    return backups

@router.get("/failed", response_model=List[BackupList])
def list_failed_backups(session: Session = Depends(get_session)):
    """
    Get a list of all backups that have a 'failed' status.
    """
    logger.info("Listing failed backups.")
    failed_backups = session.exec(select(Backup).where(Backup.status == "failed")).all()
    logger.debug(f"Found {len(failed_backups)} failed backups.")
    return failed_backups

@router.get("/{backup_id}", response_model=BackupDetail)
def get_backup_details(backup_id: str, session: Session = Depends(get_session)):
    logger.info(f"Getting details for backup_id: {backup_id}")
    backup = session.get(Backup, backup_id)
    if not backup:
        logger.warning(f"Backup with id {backup_id} not found.")
        raise HTTPException(status_code=404, detail="Backup not found")
    return backup

@router.delete("/{backup_id}", status_code=204)
def delete_backup(backup_id: str):
    logger.info(f"Request to delete backup_id: {backup_id}")
    if not backup_manager.delete_backup(backup_id):
        logger.error(f"Failed to delete backup_id: {backup_id}. Check logs for details.")
        raise HTTPException(status_code=502, detail="Failed to delete backup")
    return


@router.get("/{backup_id}/download")
def download_backup(backup_id: str, session: Session = Depends(get_session)):
    logger.info(f"Request to download backup_id: {backup_id}")
    backup = session.get(Backup, backup_id)
    if not backup:
        logger.warning(f"Backup with id {backup_id} not found.")
        raise HTTPException(status_code=404, detail="Backup not found")

    if not backup.storage_path:
        logger.error(f"Backup {backup_id} has no storage_path.")
        raise HTTPException(status_code=404, detail="Backup has no file associated")

    logger.debug(f"Serving download for backup file: {backup.storage_path}")
    return storage.get_download_response(backup.storage_path)
