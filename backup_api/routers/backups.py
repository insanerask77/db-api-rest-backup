from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlmodel import Session, select
from typing import List

from ..models import Database, Backup
from ..schemas import BackupCreate, BackupInfo, BackupList, BackupDetail
from ..database import get_session
from .. import backup_manager
from ..storage import get_storage_provider
from ..config import load_config


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
