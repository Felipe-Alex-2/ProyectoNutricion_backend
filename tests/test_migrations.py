import os
from pathlib import Path
import subprocess
import sys
from sqlalchemy import create_engine, inspect, text
from app.database import Base
import app.models


def upgrade(database):
    root = Path(__file__).resolve().parents[1]
    environment = {**os.environ, 'DATABASE_URL': f'sqlite:///{database.as_posix()}', 'ENVIRONMENT': 'test'}
    result = subprocess.run([sys.executable, 'prepare_db.py'], cwd=root, env=environment, capture_output=True, text=True, timeout=60)
    assert result.returncode == 0, result.stdout + result.stderr


def test_new_database_upgrade_and_seed_are_repeatable(tmp_path):
    database = tmp_path / 'fresh.sqlite'
    upgrade(database)
    engine = create_engine(f'sqlite:///{database.as_posix()}')
    with engine.begin() as connection:
        connection.execute(text("DELETE FROM role_permissions WHERE role_id='CLIENTE'"))
    upgrade(database)
    assert set(Base.metadata.tables).issubset(inspect(engine).get_table_names())
    with engine.connect() as connection:
        assert connection.execute(text("SELECT COUNT(*) FROM role_permissions WHERE role_id='CLIENTE'")).scalar_one() == 0
        assert connection.execute(text('SELECT COUNT(*) FROM users')).scalar_one() == 0
    engine.dispose()


def test_legacy_schema_adds_session_version_without_promoting_patient(tmp_path):
    database = tmp_path / 'legacy.sqlite'
    engine = create_engine(f'sqlite:///{database.as_posix()}')
    Base.metadata.create_all(engine)
    with engine.begin() as connection:
        connection.execute(text('ALTER TABLE users DROP COLUMN session_version'))
        connection.execute(text("INSERT INTO roles(id,name,description,platform,created_at) VALUES ('CLIENTE','Paciente','Paciente','Mobile',CURRENT_TIMESTAMP)"))
        connection.execute(text("INSERT INTO users(id,email,hashed_password,full_name,role_id,is_active,is_verified,created_at,updated_at) VALUES ('old','old@example.com','hash','Old patient','CLIENTE',1,0,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)"))
    engine.dispose()
    upgrade(database)
    engine = create_engine(f'sqlite:///{database.as_posix()}')
    with engine.connect() as connection:
        user = connection.execute(text("SELECT role_id,tenant_id,session_version FROM users WHERE id='old'")).one()
        assert tuple(user) == ('CLIENTE', None, 0)
    engine.dispose()


import pytest

@pytest.mark.parametrize('scheme', ['postgres', 'postgresql', 'postgresql+psycopg', 'postgresql+psycopg2'])
def test_migrations_use_the_installed_postgresql_driver(monkeypatch, scheme):
    """Alembic and the API must both use psycopg2 without contacting a server."""
    import runpy
    from contextlib import nullcontext
    from alembic import context
    from alembic.config import Config
    from app.config import settings
    from app.database import _resolve_db_url
    from sqlalchemy.engine import make_url
    monkeypatch.setattr(settings, 'DATABASE_URL', scheme+'://test:p%40ss@db.invalid:5432/demo?sslmode=require')
    api_url = _resolve_db_url()
    recorded = {}
    monkeypatch.setattr(context, 'config', Config(), raising=False)
    monkeypatch.setattr(context, 'is_offline_mode', lambda: True)
    monkeypatch.setattr(context, 'configure', lambda **kw: recorded.update(kw))
    monkeypatch.setattr(context, 'begin_transaction', nullcontext)
    monkeypatch.setattr(context, 'run_migrations', lambda: None)
    runpy.run_path(str(Path(__file__).resolve().parents[1] / 'alembic' / 'env.py'))
    assert recorded['url'] == api_url
    parsed = make_url(api_url)
    assert parsed.drivername == 'postgresql+psycopg2'
    assert parsed.password == 'p@ss'
    assert parsed.query['sslmode'] == 'require'
    engine = create_engine(api_url)
    assert engine.dialect.driver == 'psycopg2'
    engine.dispose()
