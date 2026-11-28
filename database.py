import logging
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

logger = logging.getLogger("ruta_clara.database")


def normalize_database_url(url: str) -> str:
    """Use the installed psycopg 3 driver for PostgreSQL URLs."""
    value = (url or "").strip()
    if value.startswith("postgres://"):
        return "postgresql+psycopg://" + value[len("postgres://"):]
    if value.startswith("postgresql://"):
        return "postgresql+psycopg://" + value[len("postgresql://"):]
    return value


_raw_database_url = os.getenv("DATABASE_URL", "").strip()
DATABASE_URL = normalize_database_url(_raw_database_url or "sqlite:///./app.db")

connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, connect_args=connect_args)

logger.info("Conectando a base de datos: %s", DATABASE_URL.split("://")[0] + "://...")

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db():
    """Dependency that provides a database session per request."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
