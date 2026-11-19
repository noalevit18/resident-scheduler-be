from sqlalchemy.orm import Session
from app.models.models import OnCallDistributionMode, OnCallStation
from app.schemas.schemas import OnCallStationCreate, OnCallStationUpdateEntry
from datetime import date, datetime, timezone
from uuid import UUID


class OnCallStationRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_all(self, division_id: UUID, include_deleted: bool = False):
        query = self.db.query(OnCallStation).filter(OnCallStation.division_id == division_id)
        if not include_deleted:
            query = query.filter(OnCallStation.is_deleted.is_(False))
        return query.all()

    def get_by_id(self, station_id: int, division_id: UUID):
        return self.db.query(OnCallStation).filter(
            OnCallStation.id == station_id, OnCallStation.division_id == division_id, OnCallStation.is_deleted.is_(False),
        ).first()

    def get_by_ids(self, ids: list[int], division_id: UUID, include_deleted: bool = True) -> dict[int, OnCallStation]:
        """include_deleted=True by default: shifts need to resolve a
        soft-deleted station's name for historical display even after it
        no longer exists as an active station."""
        if not ids:
            return {}
        query = self.db.query(OnCallStation).filter(
            OnCallStation.id.in_(ids), OnCallStation.division_id == division_id,
        )
        if not include_deleted:
            query = query.filter(OnCallStation.is_deleted.is_(False))
        return {row.id: row for row in query.all()}

    def create_all(self, division_id: UUID, entries: list[OnCallStationCreate], created_by) -> list[OnCallStation]:
        """Flushed, not committed: the caller validates and commits."""
        stations = [
            OnCallStation(
                division_id=division_id, name=e.name, initials=e.initials, created_by=created_by,
                color=e.color.model_dump() if e.color else None,
                number_of_residents=e.number_of_residents,
                requires_independent=e.requires_independent,
                open_to_external=e.open_to_external,
                distribution_mode=OnCallDistributionMode(e.distribution_mode.value),
                priority_unit_id=e.priority_unit_id,
                staff_rotation_id=e.staff_rotation_id,
                required_certification_ids=e.required_certification_ids,
                rotation_length=e.rotation_length,
                rotation_start_date=e.rotation_start_date or date.today(),
                rotation_unit_ids=e.rotation_unit_ids,
            )
            for e in entries
        ]
        self.db.add_all(stations)
        self.db.flush()
        return stations

    def apply_fields(self, station: OnCallStation, entry: OnCallStationUpdateEntry) -> None:
        for field, value in entry.model_dump(exclude_unset=True, exclude={"id"}).items():
            if field == "distribution_mode":
                value = OnCallDistributionMode(value.value)
            setattr(station, field, value)

    def soft_delete(self, station: OnCallStation) -> None:
        """Soft delete: the row stays, so past shifts keep showing the station.
        It leaves its group and no unit covers it any more."""
        station.is_deleted = True
        station.deleted_at = datetime.now(timezone.utc)
        station.group_id = None
        station.unit_coverage = []

    def delete(self, station_id: int, division_id: UUID):
        obj = self.get_by_id(station_id, division_id)
        if not obj:
            return None
        self.soft_delete(obj)
        self.db.commit()
        return obj
