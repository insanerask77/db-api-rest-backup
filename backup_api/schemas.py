from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime

class DatabaseBase(BaseModel):
    config_id: Optional[str] = None
    name: str
    engine: str
    host: str
    port: int
    database_name: str
    schedule: Optional[str] = None
    retention_days: Optional[int] = None
    max_backups: Optional[int] = None
    compression: Optional[str] = "none"
    package: Optional[bool] = False

class DatabaseCreate(DatabaseBase):
    username: str
    password: str

class DatabaseUpdate(BaseModel):
    config_id: Optional[str] = None
    name: Optional[str] = None
    engine: Optional[str] = None
    host: Optional[str] = None
    port: Optional[int] = None
    username: Optional[str] = None
    password: Optional[str] = None
    database_name: Optional[str] = None
    schedule: Optional[str] = None
    retention_days: Optional[int] = None
    max_backups: Optional[int] = None
    compression: Optional[str] = None
    package: Optional[bool] = None

class DatabaseDetail(DatabaseBase):
    id: str

    class Config:
        from_attributes = True

class PackageBase(BaseModel):
    storage_path: str
    size_bytes: int
    checksum: str

class PackageList(PackageBase):
    id: str
    created_at: datetime

    class Config:
        from_attributes = True

class PackageDetail(PackageBase):
    id: str
    created_at: datetime

    class Config:
        from_attributes = True

class BackupCreate(BaseModel):
    database_id: str
    type: str

class BackupInfo(BaseModel):
    id: str
    status: str

    class Config:
        from_attributes = True

class BackupList(BaseModel):
    id: str
    database_id: str
    status: str
    started_at: datetime
    finished_at: Optional[datetime] = None

    class Config:
        from_attributes = True

class BackupDetail(BaseModel):
    id: str
    status: str
    size_bytes: Optional[int] = None
    storage_path: Optional[str] = None
    log: Optional[str] = None

    class Config:
        from_attributes = True
