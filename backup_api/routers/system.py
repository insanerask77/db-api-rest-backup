from fastapi import APIRouter, Depends, status, UploadFile, File, HTTPException
from sqlmodel import Session

from backup_api.database import engine
from backup_api.config import load_and_sync_databases, overwrite_static_config
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

@router.put("/config", status_code=status.HTTP_204_NO_CONTENT)
async def upload_config(
    session: Session = Depends(get_session),
    file: UploadFile = File(...)
):
    """
    Overwrite the static configuration from an uploaded YAML file.
    This will delete all configurations previously loaded from a config file
    and replace them with the content of the uploaded file.
    Configurations created via API will be unaffected.
    """
    if not file.filename.endswith((".yaml", ".yml")):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid file type. Please upload a .yaml or .yml file."
        )

    try:
        content = await file.read()
        overwrite_static_config(content, session)
        schedule_database_backups()
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An unexpected error occurred: {e}",
        )
