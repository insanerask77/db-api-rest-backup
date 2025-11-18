from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select
from typing import List

from ..models import Database
from ..schemas import DatabaseCreate, DatabaseDetail, DatabaseUpdate
from ..database import get_session
from ..scheduler import schedule_database_backups, scheduler
from ..logger import get_logger
from ..dependencies import get_settings

logger = get_logger(__name__)

router = APIRouter()


@router.post("", response_model=DatabaseDetail)
def register_database(db: DatabaseCreate, session: Session = Depends(get_session)):
    logger.info("Registering a new database.")
    # Exclude password from debug log
    db_dict = db.model_dump()
    db_dict.pop('password', None)
    logger.debug(f"Received database data: {db_dict}")

    new_db = Database.model_validate(db)
    session.add(new_db)
    session.commit()
    session.refresh(new_db)
    schedule_database_backups()
    logger.info(f"Successfully registered database with id: {new_db.id}")
    return new_db


@router.get("", response_model=List[DatabaseDetail])
def list_databases(session: Session = Depends(get_session)):
    logger.info("Listing all databases.")
    databases = session.exec(select(Database).where(Database.is_deleted == False)).all()
    logger.debug(f"Found {len(databases)} databases.")
    return databases


@router.get("/{database_id}", response_model=DatabaseDetail)
def get_database(database_id: str, session: Session = Depends(get_session)):
    logger.info(f"Getting database with id: {database_id}")
    db = session.get(Database, database_id)
    if not db or db.is_deleted:
        logger.warning(f"Database with id {database_id} not found.")
        raise HTTPException(status_code=404, detail="Database not found")
    return db


@router.patch("/{database_id}", response_model=DatabaseDetail)
def update_database(database_id: str, db_update: DatabaseUpdate, session: Session = Depends(get_session)):
    logger.info(f"Updating database with id: {database_id}")
    db = session.get(Database, database_id)
    if not db or db.is_deleted:
        logger.warning(f"Database with id {database_id} not found.")
        raise HTTPException(status_code=404, detail="Database not found")

    update_data = db_update.model_dump(exclude_unset=True)
    logger.debug(f"Update data for database {database_id}: {update_data}")
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
    logger.info(f"Deleting database with id: {database_id}")
    db = session.get(Database, database_id)
    if not db:
        logger.warning(f"Database with id {database_id} not found.")
        raise HTTPException(status_code=404, detail="Database not found")

    # If it's a static config, mark as deleted instead of removing
    if db.config_id:
        db.is_deleted = True
        session.add(db)
        logger.info(f"Soft-deleted database with config_id: {db.config_id}")
    else:
        session.delete(db)
        logger.info(f"Permanently deleted database with id: {database_id}")

    # Remove the job from the scheduler
    job_id = f"backup_{db.id}"
    if scheduler.get_job(job_id):
        logger.debug(f"Removing scheduler job: {job_id}")
        scheduler.remove_job(job_id)

    session.commit()
    return


@router.post("/{database_id}/reset", response_model=DatabaseDetail)
def reset_database_to_static(
    database_id: str,
    session: Session = Depends(get_session),
    settings: dict = Depends(get_settings),
):
    db = session.get(Database, database_id)
    if not db:
        raise HTTPException(status_code=404, detail="Database not found")

    if not db.config_id:
        raise HTTPException(
            status_code=400,
            detail="This operation is only valid for databases managed by the static config.yaml."
        )

    db_configs = settings.get("databases", [])
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
