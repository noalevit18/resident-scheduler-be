from sqlalchemy.orm import Session
from app.models.models import OnCallStation
from app.schemas.schemas import OnCallStationCreate, OnCallStationUpdateEntry
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
        stations = [OnCallStation(division_id=division_id, name=e.name, created_by=created_by) for e in entries]
        self.db.add_all(stations)
        self.db.commit()
        return stations

    def update_all(
        self, stations_by_id: dict[int, OnCallStation],
        entries: list[OnCallStationUpdateEntry], deleted_ids: set[int],
    ) -> list[OnCallStation]:
        for entry in entries:
            station = stations_by_id[entry.id]
            for field, value in entry.model_dump(exclude_unset=True, exclude={"id"}).items():
                setattr(station, field, value)
        for station_id in deleted_ids:
            stations_by_id[station_id].is_deleted = True
        self.db.commit()
        return list(stations_by_id.values())

    def delete(self, station_id: int, division_id: UUID):
        obj = self.get_by_id(station_id, division_id)
        if not obj:
            return None
        obj.is_deleted = True
        self.db.commit()
        return obj
