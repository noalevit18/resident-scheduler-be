import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware 
from app.routers import (
    staff_router, station_router, senior_router, shift_router, 
    constraint_router, schedule_router, user_router, metadata_router
)
from app.database import engine
from app.models import models

app = FastAPI(title="Resident Scheduler API")

# Create tables
models.Base.metadata.create_all(bind=engine)


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

app.include_router(user_router.router)
app.include_router(staff_router.router)
app.include_router(station_router.router)
app.include_router(senior_router.router)
app.include_router(shift_router.router)
app.include_router(constraint_router.router)
app.include_router(schedule_router.router)
app.include_router(metadata_router.router)

@app.get("/")
def read_root():
    return {"message": "Welcome to the Resident Scheduler API"}

