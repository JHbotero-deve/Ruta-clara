import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from database import engine
from src.models import Base
from src.routes import router

# Create database tables automatically
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Ruta Clara API",
    description="Production-ready FastAPI service for route optimization and location management with offline interactive map.",
    version="1.0.0"
)

# Mount local static files (CSS, JS) for 100% offline capability
app.mount("/static", StaticFiles(directory="static"), name="static")

# Configure CORS Middleware for production and local development
origins = os.getenv("ALLOWED_ORIGINS", "*").split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)


@app.get("/", tags=["Root"])
def read_root():
    return RedirectResponse(url="/map")


@app.get("/map", tags=["Frontend"], response_class=FileResponse)
def serve_map():
    """Serves the offline interactive visualizer."""
    return FileResponse("index.html")


@app.get("/health", tags=["Health"])
def health_check():
    return {"status": "ok"}
