from fastapi import APIRouter, Depends, status
from sqlmodel import Session

from backup_api.database import engine
from backup_api.config import load_and_sync_databases
from backup_api.scheduler import schedule_database_backups

router = APIRouter()

def get_session():
    with Session(engine) as session:
        yield session

@router.post("/reload-databases", status_code=status.HTTP_204_NO_CONTENT)
def reload_databases_config(session: Session = Depends(get_session)):
    """Reload database configurations from config.yaml and update scheduler."""
    load_and_sync_databases(session)
    schedule_database_backups()
