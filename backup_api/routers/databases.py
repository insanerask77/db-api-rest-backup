from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks, UploadFile, File
from sqlmodel import Session, select
from typing import List
import tempfile
import shutil
import os

from ..models import Database, Restore
from ..schemas import DatabaseCreate, DatabaseDetail, DatabaseUpdate
from ..database import get_session
from ..scheduler import schedule_database_backups, scheduler
from ..dependencies import get_settings
from ..restore_manager import run_restore

router = APIRouter()

@router.post("", response_model=DatabaseDetail)
def register_database(db: DatabaseCreate, session: Session = Depends(get_session)):
    new_db = Database.from_orm(db)
    session.add(new_db)
    session.commit()
    session.refresh(new_db)
    schedule_database_backups()
    return new_db

@router.get("", response_model=List[DatabaseDetail])
def list_databases(session: Session = Depends(get_session)):
    databases = session.exec(select(Database).where(Database.is_deleted == False)).all()
    return databases

@router.get("/{database_id}", response_model=DatabaseDetail)
def get_database(database_id: str, session: Session = Depends(get_session)):
    db = session.get(Database, database_id)
    if not db or db.is_deleted:
        raise HTTPException(status_code=404, detail="Database not found")
    return db

@router.patch("/{database_id}", response_model=DatabaseDetail)
def update_database(database_id: str, db_update: DatabaseUpdate, session: Session = Depends(get_session)):
    db = session.get(Database, database_id)
    if not db or db.is_deleted:
        raise HTTPException(status_code=404, detail="Database not found")

    update_data = db_update.dict(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db, key, value)

    if db.config_id:
        db.override_static_config = True

    session.add(db)
    session.commit()
    session.refresh(db)

    schedule_database_backups()

    return db

@router.delete("/{database_id}", status_code=204)
def delete_database(database_id: str, session: Session = Depends(get_session)):
    db = session.get(Database, database_id)
    if not db or db.is_deleted:
        raise HTTPException(status_code=404, detail="Database not found")

    # Remove the job from the scheduler
    job_id = f"backup_{db.id}"
    if scheduler.get_job(job_id):
        scheduler.remove_job(job_id)

    # If it's a static config, mark as deleted; otherwise, delete permanently
    if db.config_id:
        db.is_deleted = True
        db.override_static_config = True
        session.add(db)
        session.commit()
    else:
        session.delete(db)
        session.commit()
    return


@router.post("/{database_id}/reset", response_model=DatabaseDetail)
def reset_database_to_static(database_id: str, session: Session = Depends(get_session)):
    from ..config import load_config

    db = session.get(Database, database_id)
    if not db:
        raise HTTPException(status_code=404, detail="Database not found")

    if not db.config_id:
        raise HTTPException(
            status_code=400,
            detail="This operation is only valid for databases managed by the static config.yaml."
        )

    config_data = load_config()
    db_configs = config_data.get("databases", [])
    static_config = next((c for c in db_configs if c.get('id') == db.config_id), None)

    if static_config:
        # Reset the database to the static configuration
        static_config.pop('id', None)
        for key, value in static_config.items():
            setattr(db, key, value)

        db.override_static_config = False
        db.is_deleted = False

        session.add(db)
        session.commit()
        session.refresh(db)

        schedule_database_backups()

        return db
    else:
        # If the config no longer exists in yaml, delete it permanently
        job_id = f"backup_{db.id}"
        if scheduler.get_job(job_id):
            scheduler.remove_job(job_id)

        session.delete(db)
        session.commit()
        raise HTTPException(
            status_code=404,
            detail="The original static configuration for this database no longer exists in config.yaml. "
                   "The database has been permanently deleted."
        )


def check_restore_mode(settings: dict = Depends(get_settings)):
    if not settings.get("restore_mode"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Restore mode is not enabled in the configuration.",
        )

@router.post("/{database_id}/restore-from-upload", status_code=status.HTTP_202_ACCEPTED, dependencies=[Depends(check_restore_mode)])
async def restore_from_upload(
    database_id: str,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    session: Session = Depends(get_session),
):
    """
    Restore a database from an uploaded backup file.
    """
    db = session.get(Database, database_id)
    if not db or db.is_deleted:
        raise HTTPException(status_code=404, detail="Database not found")

    restore = Restore(database_id=db.id)
    session.add(restore)
    session.commit()
    session.refresh(restore)

    temp_file = tempfile.NamedTemporaryFile(delete=False)

    try:
        with temp_file as buffer:
            shutil.copyfileobj(file.file, buffer)

        background_tasks.add_task(
            run_restore,
            db_session=session,
            restore_id=restore.id,
            db=db,
            backup_file_path=temp_file.name,
        )
        background_tasks.add_task(os.unlink, temp_file.name)

    except Exception as e:
        os.unlink(temp_file.name)
        restore.status = "failed"
        restore.error_summary = f"Failed to prepare restore from upload: {e}"
        session.add(restore)
        session.commit()
        raise HTTPException(status_code=500, detail=f"Failed to start restore process: {e}")
    finally:
        file.file.close()

    return {"message": "Restore process started.", "restore_id": restore.id}
