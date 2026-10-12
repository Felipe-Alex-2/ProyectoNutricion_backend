import os
import sys
from pathlib import Path
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient

os.environ.update(DATABASE_URL='sqlite://', ENVIRONMENT='test', SECRET_KEY='isolated-test-key-at-least-32-characters', BACKUP_ENCRYPTION_KEY='isolated-test-backup-key', SMTP_HOST='', GEMINI_API_KEY='', PAYPAL_CLIENT_ID='', PAYPAL_CLIENT_SECRET='')
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.database import Base, get_db
from app.main import app

@pytest.fixture
def db_session(tmp_path, monkeypatch):
    from app.services import backup_service
    monkeypatch.setattr(backup_service, 'BACKUP_DIR', str(tmp_path / 'backups'))
    engine = create_engine('sqlite://', connect_args={'check_same_thread': False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    with sessionmaker(bind=engine)() as db:
        yield db
    engine.dispose()

@pytest.fixture
def client(db_session):
    app.dependency_overrides[get_db] = lambda: db_session
    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.clear()
