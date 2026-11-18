import logging
import os

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

logger = logging.getLogger("ruta_clara.database")

RAILWAY_VOLUME_MOUNT_PATH = os.getenv("RAILWAY_VOLUME_MOUNT_PATH")
DEFAULT_DATABASE_URL = "sqlite:////app/data/app.db" if os.getenv("RAILWAY_ENVIRONMENT") and RAILWAY_VOLUME_MOUNT_PATH else "sqlite:///./app.db"
DATABASE_URL = os.getenv("DATABASE_URL", DEFAULT_DATABASE_URL)

if os.getenv("RAILWAY_ENVIRONMENT") and DATABASE_URL.startswith("sqlite"):
    if not RAILWAY_VOLUME_MOUNT_PATH:
        logger.critical("Railway no tiene un volumen persistente montado; SQLite está usando almacenamiento efímero y los datos pueden perderse al desplegar.")
    else:
        database_path = DATABASE_URL.removeprefix("sqlite:///")
        resolved_path = os.path.abspath(database_path)
        mount_path = os.path.abspath(RAILWAY_VOLUME_MOUNT_PATH)
        if os.path.commonpath([resolved_path, mount_path]) != mount_path:
            logger.critical("SQLite está fuera del volumen persistente de Railway (%s); revisa DATABASE_URL.", RAILWAY_VOLUME_MOUNT_PATH)

# Use check_same_thread = False only for SQLite
connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(
    DATABASE_URL,
    connect_args=connect_args,
)

logger.info("Conectando a base de datos: %s", DATABASE_URL.split("://")[0] + "://...")

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)


def get_db():
    """Dependency that provides a database session per request."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
