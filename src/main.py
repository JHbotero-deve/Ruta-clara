import logging
import os
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import inspect

from database import engine, SessionLocal
from src.models import Base, DeliveryRoute, Location, User
from src.routes import router

# Load environment variables from .env file
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("ruta_clara")


def init_db_and_migrate():
    """Create tables and apply incremental SQLite migrations if needed."""
    Base.metadata.create_all(bind=engine)

    # Migraciones compatibles con SQLite y PostgreSQL.
    with engine.begin() as conn:
        inspector = inspect(conn)
        tables = set(inspector.get_table_names())
        if "locations" in tables:
            existing_cols = {column["name"] for column in inspector.get_columns("locations")}
            migrations = {
                "route_id": "INTEGER REFERENCES delivery_routes(id)",
                "entrance_name": "VARCHAR(150)",
                "entrance_confirmed": "BOOLEAN NOT NULL DEFAULT FALSE",
                "location_source": "VARCHAR(30)",
                "client_id": "VARCHAR(64)",
                "delivered": "BOOLEAN NOT NULL DEFAULT FALSE",
                "status": "VARCHAR(30) NOT NULL DEFAULT 'pending'",
                "created_by_id": "INTEGER",
                "status_updated_by_id": "INTEGER",
                "created_at": "TIMESTAMP",
                "updated_at": "TIMESTAMP"
            }
            for column, definition in migrations.items():
                if column not in existing_cols:
                    conn.exec_driver_sql(f"ALTER TABLE locations ADD COLUMN {column} {definition}")
            conn.exec_driver_sql("CREATE UNIQUE INDEX IF NOT EXISTS ix_locations_client_id ON locations(client_id)")
            conn.exec_driver_sql("UPDATE locations SET status = CASE WHEN delivered = TRUE THEN 'delivered' ELSE 'pending' END WHERE status IS NULL OR status = '' OR (status = 'pending' AND delivered = TRUE)")
            conn.exec_driver_sql("UPDATE locations SET created_at = CURRENT_TIMESTAMP WHERE created_at IS NULL")
            conn.exec_driver_sql("UPDATE locations SET updated_at = COALESCE(created_at, CURRENT_TIMESTAMP) WHERE updated_at IS NULL")
        if "users" in tables:
            user_cols = {column["name"] for column in inspector.get_columns("users")}
            if "role" not in user_cols:
                conn.exec_driver_sql("ALTER TABLE users ADD COLUMN role VARCHAR(20) NOT NULL DEFAULT 'operator'")

    # Promoción explícita y controlada del administrador inicial.
    db = SessionLocal()
    try:
        initial_admin = os.getenv("INITIAL_ADMIN_USERNAME", "").strip()
        if initial_admin:
            admin_user = db.query(User).filter(User.username == initial_admin).first()
            if admin_user and admin_user.role != "admin":
                admin_user.role = "admin"
                db.commit()
                logger.info("Rol administrador asignado por INITIAL_ADMIN_USERNAME.")
            elif not admin_user:
                logger.warning("INITIAL_ADMIN_USERNAME no coincide con un usuario existente.")
        route_count = db.query(DeliveryRoute).count()
        if route_count == 0:
            default_route = DeliveryRoute(name="Ruta Principal 1", is_active=True)
            db.add(default_route)
            db.commit()
            db.refresh(default_route)
            logger.info("Ruta predeterminada creada: %s (id=%d)", default_route.name, default_route.id)

            # Assign existing locations to default route
            db.query(Location).filter(Location.route_id.is_(None)).update(
                {Location.route_id: default_route.id},
                synchronize_session=False
            )
            db.commit()
    except Exception as e:
        logger.error("Error asegurando ruta inicial: %s", e)
    finally:
        db.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events."""
    # Startup
    init_db_and_migrate()
    logger.info("Base de datos inicializada y migrada correctamente.")
    logger.info("Ruta Clara lista en http://127.0.0.1:8000/map")
    yield
    # Shutdown
    logger.info("Ruta Clara apagándose...")


app = FastAPI(
    title="Ruta Clara API",
    description="Production-ready FastAPI service for route optimization and location management with offline interactive map.",
    version="1.1.0",
    lifespan=lifespan,
)

# Mount local static files (CSS, JS) for 100% offline capability
app.mount("/static", StaticFiles(directory="static"), name="static")

# Configure CORS Middleware for production and local development
raw_origins = os.getenv("ALLOWED_ORIGINS", "*")
origins = [o.strip() for o in raw_origins.split(",") if o.strip()]
allow_all_origins = "*" in origins

if allow_all_origins:
    logger.warning(
        "CORS configurado con ALLOWED_ORIGINS='*'. "
        "Configura orígenes específicos en .env para producción."
    )

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if allow_all_origins else origins,
    allow_credentials=not allow_all_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(GZipMiddleware, minimum_size=500)

app.include_router(router)


@app.get("/", tags=["Root"])
def read_root():
    return RedirectResponse(url="/map")


@app.get("/map", tags=["Frontend"], response_class=FileResponse)
def serve_map():
    """Serves the offline interactive visualizer with no-cache headers."""
    return FileResponse(
        "index.html",
        headers={
            "Cache-Control": "no-cache, no-store, must-revalidate, max-age=0",
            "Pragma": "no-cache",
            "Expires": "0"
        }
    )


@app.get("/health", tags=["Health"])
def health_check():
    return {"status": "ok", "version": "1.1.0"}
