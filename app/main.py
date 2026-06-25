from fastapi import FastAPI
from routers import (
    resident_router, station_router, senior_router, shift_router, 
    constraint_router, schedule_router, account_admin_router
)
from database import engine
from models import models

# Create tables
models.Base.metadata.create_all(bind=engine)

app = FastAPI(title="Resident Scheduler API")

app.include_router(account_admin_router.router)
app.include_router(resident_router.router)
app.include_router(station_router.router)
app.include_router(senior_router.router)
app.include_router(shift_router.router)
app.include_router(constraint_router.router)
app.include_router(schedule_router.router)

@app.get("/")
def read_root():
    return {"message": "Welcome to the Resident Scheduler API"}
