from fastapi import FastAPI, HTTPException, BackgroundTasks
from typing import List, Dict
from backup_api.models import Database, Backup
from backup_api.schemas import (
    DatabaseCreate,
    DatabaseInfo,
    BackupCreate,
    BackupInfo,
    BackupList,
    BackupDetail,
)
from . import backup_manager

app = FastAPI()

# In-memory storage
databases: Dict[str, Database] = {}
backups: Dict[str, Backup] = {}


@app.post("/databases", response_model=DatabaseInfo)
def register_database(db: DatabaseCreate):
    """
    Register a new database to be backed up.
    """
    new_db = Database(**db.dict())
    databases[new_db.id] = new_db
    return {"id": new_db.id, "name": new_db.name}


@app.post("/backups", response_model=BackupInfo)
def create_backup(backup_req: BackupCreate, background_tasks: BackgroundTasks):
    """
    Create a new backup for a registered database.
    """
    database = databases.get(backup_req.database_id)
    if not database:
        raise HTTPException(status_code=404, detail="Database not found")

    new_backup = Backup(database_id=backup_req.database_id, type=backup_req.type)
    backups[new_backup.id] = new_backup

    background_tasks.add_task(backup_manager.run_backup, new_backup.id, database, backups)

    return {"backup_id": new_backup.id, "status": new_backup.status}


@app.get("/backups", response_model=List[BackupList])
def list_backups():
    """
    List all backups.
    """
    backup_list = []
    for backup_id, backup in backups.items():
        backup_list.append(
            BackupList(
                backup_id=backup.id,
                database_id=backup.database_id,
                status=backup.status,
                started_at=backup.started_at,
                finished_at=backup.finished_at,
            )
        )
    return backup_list


@app.get("/backups/{backup_id}", response_model=BackupDetail)
def get_backup_details(backup_id: str):
    """
    Get the details of a specific backup.
    """
    if backup_id not in backups:
        raise HTTPException(status_code=404, detail="Backup not found")

    backup = backups[backup_id]

    return BackupDetail(
        backup_id=backup.id,
        status=backup.status,
        size_bytes=backup.size_bytes,
        storage_path=backup.storage_path,
    )
