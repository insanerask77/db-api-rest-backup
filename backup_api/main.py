from fastapi import FastAPI
from sqlmodel import Session
from prometheus_fastapi_instrumentator import Instrumentator

from . import config
from .database import create_db_and_tables, engine
from .scheduler import scheduler, schedule_database_backups, schedule_system_jobs, initialize_metrics
from .routers import databases, backups
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()
Instrumentator().instrument(app).expose(app)

@app.on_event("startup")
def startup_event():
    create_db_and_tables()
    with Session(engine) as session:
        config.load_and_sync_databases(session)

    scheduler.start()
    schedule_database_backups()
    schedule_system_jobs()
    initialize_metrics()

@app.on_event("shutdown")
def shutdown_event():
    scheduler.shutdown()

app.include_router(databases.router, prefix="/databases", tags=["databases"])
app.include_router(backups.router, prefix="/backups", tags=["backups"])
