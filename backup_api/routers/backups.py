from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, status
from sqlmodel import Session, select
from typing import List
import tempfile
import os

from ..models import Database, Backup, Restore
from ..schemas import BackupCreate, BackupInfo, BackupList, BackupDetail
from ..database import get_session
from .. import backup_manager
from ..storage import get_storage_provider, StorageProvider
from ..config import load_config
from ..dependencies import get_settings
from ..restore_manager import run_restore


router = APIRouter()
config = load_config()
storage = get_storage_provider(config)

@router.post("", response_model=BackupInfo)
def create_backup(backup_req: BackupCreate, background_tasks: BackgroundTasks, session: Session = Depends(get_session)):
    database = session.get(Database, backup_req.database_id)
    if not database:
        raise HTTPException(status_code=404, detail="Database not found")

    new_backup = Backup(database_id=database.id, type=backup_req.type)
    session.add(new_backup)
    session.commit()
    session.refresh(new_backup)

    background_tasks.add_task(backup_manager.run_backup, new_backup.id, database.id)

    return new_backup

@router.get("", response_model=List[BackupList])
def list_backups(session: Session = Depends(get_session)):
    backups = session.exec(select(Backup)).all()
    return backups

@router.get("/failed", response_model=List[BackupList])
def list_failed_backups(session: Session = Depends(get_session)):
    """
    Get a list of all backups that have a 'failed' status.
    """
    failed_backups = session.exec(select(Backup).where(Backup.status == "failed")).all()
    return failed_backups

@router.get("/{backup_id}", response_model=BackupDetail)
def get_backup_details(backup_id: str, session: Session = Depends(get_session)):
    backup = session.get(Backup, backup_id)
    if not backup:
        raise HTTPException(status_code=404, detail="Backup not found")
    return backup

@router.delete("/{backup_id}", status_code=204)
def delete_backup(backup_id: str):
    if not backup_manager.delete_backup(backup_id):
        raise HTTPException(status_code=502, detail="Failed to delete backup")
    return


@router.get("/{backup_id}/download")
def download_backup(backup_id: str, session: Session = Depends(get_session)):
    backup = session.get(Backup, backup_id)
    if not backup:
        raise HTTPException(status_code=404, detail="Backup not found")

    if not backup.storage_path:
        raise HTTPException(status_code=404, detail="Backup has no file associated")

    return storage.get_download_response(backup.storage_path)


def check_restore_mode(settings: dict = Depends(get_settings)):
    if not settings.get("restore_mode"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Restore mode is not enabled in the configuration.",
        )

@router.post("/{backup_id}/restore", status_code=status.HTTP_202_ACCEPTED, dependencies=[Depends(check_restore_mode)])
async def restore_from_backup(
    backup_id: str,
    background_tasks: BackgroundTasks,
    session: Session = Depends(get_session),
    storage: StorageProvider = Depends(get_storage_provider),
):
    """
    Restore a database from an existing backup.
    """
    backup = session.get(Backup, backup_id)
    if not backup:
        raise HTTPException(status_code=404, detail="Backup not found")

    db = session.get(Database, backup.database_id)
    if not db:
        raise HTTPException(status_code=404, detail="Database not found for this backup")

    restore = Restore(database_id=db.id, backup_id=backup.id)
    session.add(restore)
    session.commit()
    session.refresh(restore)

    temp_file = tempfile.NamedTemporaryFile(delete=False)

    # It's crucial to wrap the download and task scheduling in a try/except/finally
    # to ensure the temporary file is always cleaned up.
    try:
        storage.download_file(backup.storage_path, temp_file.name)

        # Add the main restore task
        background_tasks.add_task(
            run_restore,
            db_session=session,
            restore_id=restore.id,
            db=db,
            backup_file_path=temp_file.name,
        )

        # Add the cleanup task, which will run after the restore task
        background_tasks.add_task(os.unlink, temp_file.name)

    except Exception as e:
        # If setup fails, clean up immediately and fail the restore operation
        os.unlink(temp_file.name)
        restore.status = "failed"
        restore.error_summary = f"Failed to prepare restore: {e}"
        session.add(restore)
        session.commit()
        raise HTTPException(status_code=500, detail=f"Failed to start restore process: {e}")

    return {"message": "Restore process started.", "restore_id": restore.id}
