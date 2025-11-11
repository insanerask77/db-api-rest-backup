from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime

class DatabaseCreate(BaseModel):
    name: str
    engine: str
    host: str
    port: int
    username: str
    password: str
    database_name: str
    schedule: Optional[str] = None
    retention_days: Optional[int] = None

class DatabaseUpdate(BaseModel):
    schedule: Optional[str] = None
    retention_days: Optional[int] = None

class DatabaseInfo(BaseModel):
    id: str
    name: str

class BackupCreate(BaseModel):
    database_id: str
    type: str

class BackupInfo(BaseModel):
    backup_id: str
    status: str

class BackupList(BaseModel):
    backup_id: str
    database_id: str
    status: str
    started_at: datetime
    finished_at: Optional[datetime] = None

class BackupDetail(BaseModel):
    backup_id: str
    status: str
    size_bytes: Optional[int] = None
    storage_path: Optional[str] = None
