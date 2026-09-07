"""
Database configuration — lazy initialisation.

The SQLAlchemy `engine` and `SessionLocal` are created **on first access**,
not at module-import time. This prevents the backend from crashing on
Railway if `DATABASE_URL` is not yet available when the module is
first imported (e.g. during `run.py` or early module graph resolution).
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

Base = declarative_base()

# --------------- internal state (module-level singletons) ---------------
_engine = None
_SessionLocal = None


def _resolve_db_url() -> str:
    """Return a validated, driver-prefixed database URL."""
    from app.config import settings

    db_url = (settings.DATABASE_URL or "").strip().strip('"').strip("'")

    if not db_url:
        raise ValueError(
            "DATABASE_URL is empty. "
            "Set it in Railway → Variables (e.g. postgresql://postgres:pass@host:5432/railway)."
        )

    if db_url.startswith("${{"):
        raise ValueError(
            f"DATABASE_URL is not expanded by Railway: received literal '{db_url}'. "
            "Paste the actual Postgres connection URL directly in Railway → Variables."
        )

    # Ensure the psycopg2 driver is used
    if db_url.startswith("postgres://"):
        db_url = db_url.replace("postgres://", "postgresql+psycopg2://", 1)
    elif db_url.startswith("postgresql://") and not db_url.startswith("postgresql+"):
        db_url = db_url.replace("postgresql://", "postgresql+psycopg2://", 1)

    return db_url


def get_engine():
    """Return (and lazily create) the global SQLAlchemy engine."""
    global _engine
    if _engine is None:
        db_url = _resolve_db_url()
        connect_args = {}
        if db_url.startswith("sqlite"):
            connect_args = {"check_same_thread": False}

        _engine = create_engine(
            db_url,
            connect_args=connect_args,
            pool_pre_ping=True,
        )
        print(f"[database] Engine created for: {db_url.split('@')[-1] if '@' in db_url else '(local)'}")
    return _engine


def get_session_local():
    """Return (and lazily create) the global sessionmaker."""
    global _SessionLocal
    if _SessionLocal is None:
        _SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=get_engine())
    return _SessionLocal


# --------------- Backward-compatible aliases ---------------
# Many modules do `from app.database import engine, SessionLocal`.
# These properties are resolved lazily via a module-level __getattr__.

def __getattr__(name):
    if name == "engine":
        return get_engine()
    if name == "SessionLocal":
        return get_session_local()
    raise AttributeError(f"module 'app.database' has no attribute {name!r}")


# --------------- FastAPI dependency ---------------

def get_db():
    """Dependency for obtaining database session."""
    Session = get_session_local()
    db = Session()
    try:
        yield db
    finally:
        db.close()
