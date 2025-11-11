from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
import uuid

class Database(BaseModel):
    id: str = Field(default_factory=lambda: f"db_{uuid.uuid4().hex[:6]}")
    name: str
    engine: str
    host: str
    port: int
    username: str
    password: str
    database_name: str

class Backup(BaseModel):
    id: str = Field(default_factory=lambda: f"bkp_{uuid.uuid4().hex[:6]}")
    database_id: str
    type: str
    status: str = "running"
    started_at: datetime = Field(default_factory=datetime.utcnow)
    finished_at: Optional[datetime] = None
    size_bytes: Optional[int] = None
    storage_path: Optional[str] = None
    checksum: Optional[str] = None
