from pydantic import BaseModel
from typing import List
from uuid import UUID

class ScheduleStationResidents(BaseModel):
    station_id: int
    staff_member_ids: List[UUID]

class ScheduleCreate(BaseModel):
    account_id: UUID
    senior_id: int
    stations: List[ScheduleStationResidents]

class ScheduleResponse(ScheduleCreate):
    pass
