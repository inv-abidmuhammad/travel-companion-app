"""
SQLAlchemy engine + session setup.

`engine` and `SessionLocal` are built once, at import time, from
settings — same pattern as the LLM client and the compiled graph:
build expensive/shared things once, reuse them per request.
"""
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import get_settings
from app.db.models import Base

_settings = get_settings()

engine = create_engine(_settings.sqlalchemy_database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def init_db() -> None:
    """Create tables that don't exist yet. Safe to call on every
    startup — SQLAlchemy's create_all is a no-op for tables that
    already exist. For a real production app you'd use Alembic
    migrations instead once the schema needs to evolve without data
    loss; create_all is the right level of complexity for now.
    """
    Base.metadata.create_all(bind=engine)


def get_db():
    """FastAPI dependency: `db: Session = Depends(get_db)`. Yields one
    session per request and always closes it afterward, even if the
    endpoint raises."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
