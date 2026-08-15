from fastapi import APIRouter, Depends
from app.schemas.schedule_schema import ScheduleCreate, ScheduleResponse
from app.services.schedule_service import ScheduleService
from app.dependencies import get_schedule_service

router = APIRouter(prefix="/schedule", tags=["schedule"])


@router.post("/", response_model=ScheduleResponse)
def create_schedule(data: ScheduleCreate, service: ScheduleService = Depends(get_schedule_service)):
    return service.process_schedule(data)
