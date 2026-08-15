from fastapi import APIRouter, Depends
from services.metadata_service import MetadataService
from dependencies import get_metadata_service

router = APIRouter(prefix="/metadata", tags=["metadata"])

@router.get("/")
def get_metadata(division_id: str, service: MetadataService = Depends(get_metadata_service)):
    return service.get_division_metadata(division_id=division_id)
