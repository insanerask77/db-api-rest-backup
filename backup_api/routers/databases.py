from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select
from typing import List

from ..models import Database
from ..schemas import DatabaseCreate, DatabaseInfo, DatabaseUpdate
from ..database import get_session
from ..scheduler import schedule_database_backups

router = APIRouter()

@router.post("", response_model=DatabaseInfo)
def register_database(db: DatabaseCreate, session: Session = Depends(get_session)):
    new_db = Database.from_orm(db)
    session.add(new_db)
    session.commit()
    session.refresh(new_db)
    schedule_database_backups()
    return new_db

@router.get("", response_model=List[DatabaseInfo])
def list_databases(session: Session = Depends(get_session)):
    databases = session.exec(select(Database)).all()
    return databases

@router.get("/{database_id}", response_model=DatabaseInfo)
def get_database(database_id: str, session: Session = Depends(get_session)):
    db = session.get(Database, database_id)
    if not db:
        raise HTTPException(status_code=404, detail="Database not found")
    return db

@router.patch("/{database_id}", response_model=DatabaseInfo)
def update_database_schedule(database_id: str, db_update: DatabaseUpdate, session: Session = Depends(get_session)):
    db = session.get(Database, database_id)
    if not db:
        raise HTTPException(status_code=404, detail="Database not found")

    update_data = db_update.dict(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db, key, value)

    session.add(db)
    session.commit()
    session.refresh(db)

    schedule_database_backups()

    return db
