from fastapi import FastAPI, HTTPException, BackgroundTasks, Depends
from typing import List
from sqlmodel import Session, select

from .models import Database, Backup
from .schemas import (
    DatabaseCreate,
    DatabaseInfo,
    BackupCreate,
    BackupInfo,
    BackupList,
    BackupDetail,
    DatabaseUpdate,
)
from . import backup_manager
from .scheduler import scheduler, schedule_database_backups, schedule_retention_policy
from .database import create_db_and_tables, get_session, engine
import json
import logging
import os

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()

def load_predefined_databases(session: Session):
    config_path = "config.json"
    if os.path.exists(config_path):
        logger.info(f"Found config file at '{config_path}'. Loading predefined databases.")
        with open(config_path, "r") as f:
            try:
                db_configs = json.load(f)
                for config in db_configs:
                    # Check if a database with the same name already exists
                    existing_db = session.exec(select(Database).where(Database.name == config["name"])).first()
                    if not existing_db:
                        db = Database(**config)
                        session.add(db)
                session.commit()
                logger.info(f"Successfully loaded databases from config.")
            except (json.JSONDecodeError, TypeError) as e:
                logger.error(f"Error reading or parsing config file: {e}")

@app.on_event("startup")
def startup_event():
    create_db_and_tables()
    with Session(engine) as session:
        load_predefined_databases(session)

    scheduler.start()
    schedule_database_backups()
    schedule_retention_policy()

@app.on_event("shutdown")
def shutdown_event():
    scheduler.shutdown()

@app.post("/databases", response_model=DatabaseInfo)
def register_database(db: DatabaseCreate, session: Session = Depends(get_session)):
    new_db = Database.from_orm(db)
    session.add(new_db)
    session.commit()
    session.refresh(new_db)
    schedule_database_backups()
    return new_db

@app.patch("/databases/{database_id}", response_model=DatabaseInfo)
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

@app.post("/backups", response_model=BackupInfo)
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

@app.get("/backups", response_model=List[BackupList])
def list_backups(session: Session = Depends(get_session)):
    backups = session.exec(select(Backup)).all()
    return backups

@app.get("/backups/{backup_id}", response_model=BackupDetail)
def get_backup_details(backup_id: str, session: Session = Depends(get_session)):
    backup = session.get(Backup, backup_id)
    if not backup:
        raise HTTPException(status_code=404, detail="Backup not found")
    return backup
