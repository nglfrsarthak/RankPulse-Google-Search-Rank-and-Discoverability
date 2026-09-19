"""
RankPulse - Production Application Entrypoint.
Initializes FastAPI, mounts static dashboard, attaches routers, and runs database migrations.
"""

from __future__ import annotations
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from rankpulse.api.routes import router as api_router
from rankpulse.core.config import PACKAGE_ROOT
from rankpulse.core.database import init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and shutdown hooks."""
    # Initialize DB tables on startup
    init_db()
    yield


app = FastAPI(
    title="RankPulse API",
    description="Google Search Rank & Discoverability Momentum Predictor and Editorial Triage Platform",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Attach API routes
app.include_router(api_router)

# Mount Static Dashboard
STATIC_DIR = PACKAGE_ROOT / "static"
STATIC_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/", StaticFiles(directory=str(STATIC_DIR), html=True), name="static")


if __name__ == "__main__":
    import uvicorn
    from rankpulse.core.config import API_HOST, API_PORT, DEBUG

    uvicorn.run("rankpulse.main:app", host=API_HOST, port=API_PORT, reload=DEBUG)
