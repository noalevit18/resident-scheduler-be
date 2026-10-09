from collections import defaultdict
from datetime import date, datetime, timezone
from typing import Iterable, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.models import OnCallStationMapping, ScheduleVersionStation, Station, StationVersion

# effective_from of versions that predate effective dates (migrated data).
EPOCH = date(1970, 1, 1)


def version_sort_key(version: StationVersion) -> tuple:
    return (version.effective_from, version.version)


def version_in_effect(versions: Iterable[StationVersion], on: date) -> Optional[StationVersion]:
    """The version in effect on `on`: greatest effective_from <= on, ties to
    the higher version. None when every version starts later."""
    candidates = [v for v in versions if v.effective_from <= on]
    return max(candidates, key=version_sort_key) if candidates else None


class StationRepository:
    """`stations` holds identity, the GLOBAL fields, and a mirror of the
    latest-effective version's VERSIONED fields; `station_versions` holds the
    versioned config, each effective from a date."""

    def __init__(self, db: Session):
        self.db = db

    def commit(self) -> None:
        self.db.commit()

    # --- stations ---

    def get_all(self, unit_id: UUID, include_deleted: bool = False):
        query = self.db.query(Station).filter(Station.unit_id == unit_id)
        if not include_deleted:
            query = query.filter(Station.is_deleted.is_(False))
        return query.order_by(Station.display_order.asc().nulls_last(), Station.id).all()

    def get_by_id(self, station_id: int, unit_id: UUID):
        return self.db.query(Station).filter(
            Station.id == station_id, Station.unit_id == unit_id, Station.is_deleted.is_(False),
        ).first()

    def get_by_ids(self, ids: list[int], unit_id: UUID, include_deleted: bool = True) -> dict[int, Station]:
        """include_deleted=True by default: older schedule versions keep
        referencing a station after it's been soft-deleted."""
        if not ids:
            return {}
        query = self.db.query(Station).filter(Station.id.in_(ids), Station.unit_id == unit_id)
        if not include_deleted:
            query = query.filter(Station.is_deleted.is_(False))
        return {row.id: row for row in query.all()}

    def add_station(self, unit_id: UUID, data: dict) -> Station:
        station = Station(unit_id=unit_id, **data)
        self.db.add(station)
        self.db.flush()
        return station

    def apply_fields(self, station: Station, data: dict) -> None:
        for key, value in data.items():
            setattr(station, key, value)
        self.db.flush()

    def soft_delete(self, station: Station, deleted_by: Optional[UUID]) -> None:
        """schedule_stations rows of older versions reference the station by
        FK (RESTRICT), so the row must stay."""
        station.is_deleted = True
        station.deleted_at = datetime.now(timezone.utc)
        station.deleted_by = deleted_by
        self.db.flush()

    # --- versions ---

    def get_versions(self, station_ids: list[int]) -> dict[int, list[StationVersion]]:
        """{station_id: [versions sorted by (effective_from, version)]}."""
        if not station_ids:
            return {}
        rows = (
            self.db.query(StationVersion)
            .filter(StationVersion.station_id.in_(station_ids))
            .order_by(StationVersion.station_id, StationVersion.effective_from, StationVersion.version)
            .all()
        )
        result: dict = defaultdict(list)
        for row in rows:
            result[row.station_id].append(row)
        return result

    def get_unit_versions(self, unit_id: UUID) -> dict[int, list[StationVersion]]:
        """Every station of the unit, soft-deleted ones included."""
        ids = [row[0] for row in self.db.query(Station.id).filter(Station.unit_id == unit_id).all()]
        return self.get_versions(ids)

    def get_pinned_version_ids(self, version_ids: list[int]) -> set[int]:
        if not version_ids:
            return set()
        rows = (
            self.db.query(ScheduleVersionStation.station_version_id)
            .filter(ScheduleVersionStation.station_version_id.in_(version_ids))
            .distinct()
            .all()
        )
        return {row[0] for row in rows}

    def write_version(
        self, station: Station, effective_from: date, config: dict, created_by: Optional[UUID], is_retired: bool = False,
    ) -> StationVersion:
        """Replaces the version with the same effective_from in place when no
        schedule version pins it; otherwise inserts version max+1. Then
        re-mirrors the latest-effective config onto `stations`. `config` must
        hold every versioned field — its keys are the fields mirrored. No commit."""
        versions = self.get_versions([station.id]).get(station.id, [])
        same_date = [v for v in versions if v.effective_from == effective_from]
        target = max(same_date, key=version_sort_key) if same_date else None
        if target is not None and target.id in self.get_pinned_version_ids([target.id]):
            target = None
        if target is None:
            target = StationVersion(
                station_id=station.id, version=max((v.version for v in versions), default=0) + 1,
                effective_from=effective_from,
            )
            self.db.add(target)
            versions.append(target)
        for field, value in config.items():
            setattr(target, field, value)
        target.is_retired = is_retired
        target.created_by = created_by
        self.db.flush()
        self._mirror_latest_config(station, versions, config.keys())
        return target

    def _mirror_latest_config(self, station: Station, versions: list[StationVersion], fields: Iterable[str]) -> None:
        latest = max(versions, key=version_sort_key)
        for field in fields:
            setattr(station, field, getattr(latest, field))
        self.db.flush()

    def snapshot_if_changed(
        self, station: Station, config: dict, created_by: Optional[UUID], effective_from: date = EPOCH,
    ) -> Optional[StationVersion]:
        """Used by the Firestore migration: writes `config` (the station's
        current versioned config) as a version when it has none yet or the
        latest differs, so re-runs stay idempotent. No commit."""
        versions = self.get_versions([station.id]).get(station.id, [])
        if versions:
            latest = max(versions, key=version_sort_key)
            if all(getattr(latest, field) == value for field, value in config.items()):
                return None
        return self.write_version(station, effective_from, config, created_by)

    # --- on-call mappings ---

    def get_on_call_station_ids(self, station_ids: list[int]) -> dict[int, list[int]]:
        if not station_ids:
            return {}
        rows = (
            self.db.query(OnCallStationMapping.station_id, OnCallStationMapping.on_call_station_id)
            .filter(OnCallStationMapping.station_id.in_(station_ids))
            .order_by(OnCallStationMapping.on_call_station_id)
            .all()
        )
        result: dict = defaultdict(list)
        for station_id, on_call_station_id in rows:
            result[station_id].append(on_call_station_id)
        return result

    def replace_on_call_mappings(self, unit_id: UUID, station_id: int, on_call_station_ids: list[int]) -> None:
        """An on-call station maps to at most one station per unit, so the
        given on-call stations are first detached from whatever station they
        were mapped to. No commit."""
        self.db.query(OnCallStationMapping).filter(
            OnCallStationMapping.unit_id == unit_id,
            (OnCallStationMapping.station_id == station_id)
            | OnCallStationMapping.on_call_station_id.in_(on_call_station_ids or [-1]),
        ).delete(synchronize_session=False)
        self.db.add_all([
            OnCallStationMapping(unit_id=unit_id, on_call_station_id=on_call_station_id, station_id=station_id)
            for on_call_station_id in dict.fromkeys(on_call_station_ids)
        ])
        self.db.flush()
