from typing import Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.models import OnCallDivisionSettings, OnCallStation, OnCallStationGroup, OnCallUnitStation, StaffCertification, StaffRotation, Unit


class OnCallSettingsRepository:
    """Division-level on-call settings: station groups and what each unit can cover."""

    def __init__(self, db: Session):
        self.db = db

    # --- General ---

    def get_division_settings(self, division_id: UUID) -> Optional[OnCallDivisionSettings]:
        return self.db.get(OnCallDivisionSettings, division_id)

    def add_division_settings(self, settings: OnCallDivisionSettings) -> None:
        self.db.add(settings)

    # --- Groups ---

    def get_groups(self, division_id: UUID) -> list[OnCallStationGroup]:
        return (
            self.db.query(OnCallStationGroup)
            .filter(OnCallStationGroup.division_id == division_id)
            .order_by(OnCallStationGroup.name)
            .all()
        )

    def get_group(self, group_id: int, division_id: UUID) -> Optional[OnCallStationGroup]:
        return self.db.query(OnCallStationGroup).filter(
            OnCallStationGroup.id == group_id, OnCallStationGroup.division_id == division_id,
        ).first()

    def get_group_by_name(self, name: str, division_id: UUID) -> Optional[OnCallStationGroup]:
        return self.db.query(OnCallStationGroup).filter(
            OnCallStationGroup.name == name, OnCallStationGroup.division_id == division_id,
        ).first()

    def add_group(self, group: OnCallStationGroup) -> None:
        self.db.add(group)

    def delete_group(self, group: OnCallStationGroup) -> None:
        self.db.delete(group)

    # --- Stations ---

    def active_stations(self, division_id: UUID) -> list[OnCallStation]:
        return self.db.query(OnCallStation).filter(
            OnCallStation.division_id == division_id, OnCallStation.is_deleted.is_(False),
        ).all()

    def stations_in_group(self, group_id: int) -> list[OnCallStation]:
        return self.db.query(OnCallStation).filter(
            OnCallStation.group_id == group_id, OnCallStation.is_deleted.is_(False),
        ).all()

    # --- Units ---

    def division_rotation_ids(self, division_id: UUID) -> set[int]:
        rows = self.db.query(StaffRotation.id).filter(StaffRotation.division_id == division_id).all()
        return {row.id for row in rows}

    def division_certification_ids(self, division_id: UUID) -> set[int]:
        """The staff certifications of every unit in the division."""
        rows = (
            self.db.query(StaffCertification.id)
            .join(Unit, Unit.id == StaffCertification.unit_id)
            .filter(Unit.division_id == division_id)
            .all()
        )
        return {row.id for row in rows}

    def division_unit_names(self, division_id: UUID) -> dict[UUID, str]:
        rows = self.db.query(Unit.id, Unit.name).filter(Unit.division_id == division_id).all()
        return {row.id: row.name for row in rows}

    def coverage_by_unit(self, division_id: UUID) -> dict[UUID, list[int]]:
        """Each restricted unit's coverable active stations. Units with no rows (cover everything) are absent."""
        rows = (
            self.db.query(OnCallUnitStation.unit_id, OnCallUnitStation.on_call_station_id)
            .join(OnCallStation, OnCallStation.id == OnCallUnitStation.on_call_station_id)
            .filter(OnCallStation.division_id == division_id, OnCallStation.is_deleted.is_(False))
            .order_by(OnCallUnitStation.on_call_station_id)
            .all()
        )
        coverage: dict[UUID, list[int]] = {}
        for unit_id, station_id in rows:
            coverage.setdefault(unit_id, []).append(station_id)
        return coverage

    def replace_coverage(self, unit_id: UUID, station_ids: list[int]) -> None:
        """Replaces the unit's covered stations; existing rows that stay are kept."""
        rows = self.db.query(OnCallUnitStation).filter(OnCallUnitStation.unit_id == unit_id).all()
        keep = set(station_ids)
        for row in rows:
            if row.on_call_station_id not in keep:
                self.db.delete(row)
        existing = {row.on_call_station_id for row in rows}
        for station_id in station_ids:
            if station_id not in existing:
                self.db.add(OnCallUnitStation(unit_id=unit_id, on_call_station_id=station_id))

    def add_coverage(self, unit_id: UUID, station_id: int) -> None:
        exists = self.db.query(OnCallUnitStation).filter(
            OnCallUnitStation.unit_id == unit_id, OnCallUnitStation.on_call_station_id == station_id,
        ).first()
        if exists is None:
            self.db.add(OnCallUnitStation(unit_id=unit_id, on_call_station_id=station_id))
