from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks, UploadFile, File
from typing import List
from sqlmodel import Session, select
from ..database import get_session
from ..dependencies import get_settings
from ..models import Restore, Backup, Database
from ..schemas import RestoreList, RestoreDetail
from ..restore_manager import run_restore
from ..storage import get_storage_provider, StorageProvider
import tempfile
import os

router = APIRouter(
    prefix="/restores",
    tags=["Restores"],
)

def check_restore_mode(settings: dict = Depends(get_settings)):
    if not settings.get("restore_mode"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Restore mode is not enabled in the configuration.",
        )

# Apply the dependency to all routes in this router
router.dependencies.append(Depends(check_restore_mode))

@router.get("/", response_model=List[RestoreList])
def get_all_restores(session: Session = Depends(get_session)):
    """
    Get a list of all restore operations.
    """
    restores = session.exec(select(Restore)).all()
    return restores

@router.get("/{restore_id}", response_model=RestoreDetail)
def get_restore_details(restore_id: str, session: Session = Depends(get_session)):
    """
    Get the details of a specific restore operation.
    """
    restore = session.get(Restore, restore_id)
    if not restore:
        raise HTTPException(status_code=404, detail="Restore not found")
    return restore
