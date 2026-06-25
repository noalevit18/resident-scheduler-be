from fastapi import APIRouter, Depends
from schemas.schedule_schema import ScheduleCreate, ScheduleResponse
from services.schedule_service import ScheduleService
from dependencies import get_schedule_service

router = APIRouter(prefix="/schedule", tags=["schedule"])


@router.post("/", response_model=ScheduleResponse)
def create_schedule(data: ScheduleCreate, service: ScheduleService = Depends(get_schedule_service)):
    return service.process_schedule(data)
