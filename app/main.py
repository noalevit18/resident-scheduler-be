import os
import sys
import logging
from contextlib import asynccontextmanager

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from app.logging_config import configure_logging

configure_logging()

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from app.database import engine
from app.routers import (
    staff_router, staff_settings_router, station_router, senior_router, shift_router,
    constraint_router, schedule_router, user_router, metadata_router
)

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Warm the DB connection pool at startup so the first real request
    # (typically login) doesn't pay the TCP/TLS/auth handshake cost.
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        logger.info("Successfully warmed database connection pool on startup")
    except Exception:
        logger.exception("Failed to warm database connection pool on startup")
    yield


app = FastAPI(title="Resident Scheduler API", lifespan=lifespan)

allowed_origins_raw = os.getenv("ALLOWED_CORS_ORIGINS", "http://localhost:3000")
ORIGINS = [origin.strip() for origin in allowed_origins_raw.split(",") if origin.strip()]
# Apply the middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)

app.include_router(user_router.router, prefix="/api")
app.include_router(staff_settings_router.router, prefix="/api")
app.include_router(staff_router.router, prefix="/api")
app.include_router(station_router.router, prefix="/api")
app.include_router(senior_router.router, prefix="/api")
app.include_router(shift_router.router, prefix="/api")
app.include_router(constraint_router.router, prefix="/api")
app.include_router(schedule_router.router, prefix="/api")
app.include_router(metadata_router.router, prefix="/api")

@app.get("/")
def read_root():
    return {"message": "Welcome to the Resident Scheduler API"}

