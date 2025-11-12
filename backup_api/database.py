from sqlmodel import create_engine, SQLModel, Session
import os

DATA_DIR = "data"
DATABASE_FILE = "backup.db"
DATABASE_PATH = os.path.join(DATA_DIR, DATABASE_FILE)
DATABASE_URL = f"sqlite:///{DATABASE_PATH}"

engine = create_engine(DATABASE_URL, echo=True)

def create_db_and_tables():
    # Ensure the data directory exists
    os.makedirs(DATA_DIR, exist_ok=True)
    SQLModel.metadata.create_all(engine)

def get_session():
    with Session(engine) as session:
        yield session
