import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware 
from routers import (
    staff_router, station_router, senior_router, shift_router, 
    constraint_router, schedule_router, user_router, metadata_router
)
from database import engine
from models import models

# Create tables
models.Base.metadata.create_all(bind=engine)

app = FastAPI(title="Resident Scheduler API")


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

