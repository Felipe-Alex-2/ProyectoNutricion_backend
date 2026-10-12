"""Explicit deployment step. Run before starting the API, never during requests."""
from pathlib import Path
from alembic import command
from alembic.config import Config
from sqlalchemy import inspect
from app.database import Base, get_engine
import app.models
from init_sprint1_db import init_db

def prepare_database():
    config = Config(str(Path(__file__).with_name("alembic.ini")))
    command.upgrade(config, "head")
    inspector = inspect(get_engine())
    missing = []
    for table in Base.metadata.sorted_tables:
        existing = {column["name"] for column in inspector.get_columns(table.name)}
        missing.extend(f"{table.name}.{column.name}" for column in table.columns if column.name not in existing)
    if missing:
        raise RuntimeError("Legacy schema needs a reviewed migration for missing columns: " + ", ".join(missing))
    init_db()

if __name__ == "__main__":
    prepare_database()
