from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select
from typing import List

from ..models import Database
from ..schemas import DatabaseCreate, DatabaseDetail, DatabaseUpdate
from ..database import get_session
from ..scheduler import schedule_database_backups, scheduler
from ..logger import get_logger

logger = get_logger(__name__)

router = APIRouter()

@router.post("", response_model=DatabaseDetail)
def register_database(db: DatabaseCreate, session: Session = Depends(get_session)):
    logger.info("Registering a new database.")
    # Exclude password from debug log
    db_dict = db.dict()
    db_dict.pop('password', None)
    logger.debug(f"Received database data: {db_dict}")

    new_db = Database.from_orm(db)
    session.add(new_db)
    session.commit()
    session.refresh(new_db)
    schedule_database_backups()
    logger.info(f"Successfully registered database with id: {new_db.id}")
    return new_db

@router.get("", response_model=List[DatabaseDetail])
def list_databases(session: Session = Depends(get_session)):
    logger.info("Listing all databases.")
    databases = session.exec(select(Database)).all()
    logger.debug(f"Found {len(databases)} databases.")
    return databases

@router.get("/{database_id}", response_model=DatabaseDetail)
def get_database(database_id: str, session: Session = Depends(get_session)):
    logger.info(f"Getting database with id: {database_id}")
    db = session.get(Database, database_id)
    if not db:
        logger.warning(f"Database with id {database_id} not found.")
        raise HTTPException(status_code=404, detail="Database not found")
    return db

@router.patch("/{database_id}", response_model=DatabaseDetail)
def update_database(database_id: str, db_update: DatabaseUpdate, session: Session = Depends(get_session)):
    logger.info(f"Updating database with id: {database_id}")
    db = session.get(Database, database_id)
    if not db:
        logger.warning(f"Database with id {database_id} not found.")
        raise HTTPException(status_code=404, detail="Database not found")

    update_data = db_update.dict(exclude_unset=True)
    logger.debug(f"Update data for database {database_id}: {update_data}")
    for key, value in update_data.items():
        setattr(db, key, value)

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

    # Remove the job from the scheduler
    job_id = f"backup_{db.id}"
    if scheduler.get_job(job_id):
        logger.debug(f"Removing scheduler job: {job_id}")
        scheduler.remove_job(job_id)

    session.delete(db)
    session.commit()
    logger.info(f"Successfully deleted database with id: {database_id}")
    return
