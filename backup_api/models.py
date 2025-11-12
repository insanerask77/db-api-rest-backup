from typing import Optional
from datetime import datetime
from sqlmodel import Field, SQLModel
import uuid

class Database(SQLModel, table=True):
    id: str = Field(default_factory=lambda: f"db_{uuid.uuid4().hex[:6]}", primary_key=True)
    name: str
    engine: str
    host: str
    port: int
    username: str
    password: str
    database_name: str
    schedule: Optional[str] = None
    retention_days: Optional[int] = None
    max_backups: Optional[int] = None
    compression: str = "none"

class Backup(SQLModel, table=True):
    id: str = Field(default_factory=lambda: f"bkp_{uuid.uuid4().hex[:6]}", primary_key=True)
    database_id: str = Field(foreign_key="database.id")
    type: str
    status: str = "running"
    started_at: datetime = Field(default_factory=datetime.utcnow)
    finished_at: Optional[datetime] = None
    size_bytes: Optional[int] = None
    storage_path: Optional[str] = None
    checksum: Optional[str] = None
    log: Optional[str] = None
