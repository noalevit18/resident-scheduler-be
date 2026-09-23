import logging
from uuid import UUID

from sqlalchemy.exc import IntegrityError

from app.repositories.on_call_station_repository import OnCallStationRepository
from app.schemas.schemas import OnCallStationsCreate, OnCallStationsUpdate
from app.context import get_current_user_label

logger = logging.getLogger(__name__)


class OnCallStationNameConflictError(Exception):
    def __init__(self, code: str, message: str):
        self.code = code
        self.message = message
        super().__init__(message)


class OnCallStationService:
    def __init__(self, repository: OnCallStationRepository):
        self.repository = repository

    def get_all(self, division_id: UUID, include_deleted: bool = False):
        return self.repository.get_all(division_id, include_deleted=include_deleted)

    def get_by_ids(self, ids: list[int], division_id: UUID, include_deleted: bool = True):
        return self.repository.get_by_ids(ids, division_id, include_deleted=include_deleted)

    def create_all(self, division_id: UUID, data: OnCallStationsCreate, created_by):
        """Validates every name against current active stations and
        against each other up front (one query), then inserts everything
        in a single batch (one commit) instead of one round trip per
        entry."""
        existing_names = {s.name for s in self.repository.get_all(division_id, include_deleted=False)}
        seen_names = set()
        for entry in data.entries:
            if entry.name in existing_names or entry.name in seen_names:
                raise OnCallStationNameConflictError(
                    "on_call_station_duplicate_name", f"An active station named '{entry.name}' already exists"
                )
            seen_names.add(entry.name)

        try:
            created = self.repository.create_all(division_id, data.entries, created_by)
        except IntegrityError as e:
            self.repository.db.rollback()
            raise OnCallStationNameConflictError(
                "on_call_station_duplicate_name", "One or more station names already exist"
            ) from e

        for station in created:
            logger.info("Created on-call station %s (division_id=%s) by %s", station.name, division_id, get_current_user_label())
        return created

    def update_all(self, division_id: UUID, data: OnCallStationsUpdate):
        """Validates existence and name conflicts up front against a single
        fetch of every touched station plus current active names, then
        applies every rename/delete in one batch (one commit) instead of
        one round trip per entry. `data.deleted` station ids are
        soft-deleted in the same call; deleted stations are appended to
        the returned list too."""
        deleted_ids = set(data.deleted)
        target_ids = {entry.id for entry in data.entries} | deleted_ids
        if not target_ids:
            return []

        stations_by_id = self.repository.get_by_ids(list(target_ids), division_id, include_deleted=True)
        missing = target_ids - set(stations_by_id.keys())
        if missing:
            raise ValueError(f"On-call station(s) not found: {sorted(missing)}")

        # A name still held by a station that's also being deleted in this
        # same call isn't a real conflict — it's being freed up.
        active_names = {
            s.name: s.id for s in self.repository.get_all(division_id, include_deleted=False)
            if s.id not in deleted_ids
        }
        target_names: dict[str, int] = {}
        for entry in data.entries:
            if entry.name is None:
                continue
            conflicting_id = active_names.get(entry.name, target_names.get(entry.name))
            if conflicting_id is not None and conflicting_id != entry.id:
                raise OnCallStationNameConflictError(
                    "on_call_station_duplicate_name", f"An active station named '{entry.name}' already exists"
                )
            target_names[entry.name] = entry.id

        try:
            updated = self.repository.update_all(stations_by_id, data.entries, deleted_ids)
        except IntegrityError as e:
            self.repository.db.rollback()
            raise OnCallStationNameConflictError(
                "on_call_station_duplicate_name", "One or more station names already exist"
            ) from e

        for entry in data.entries:
            logger.info(
                "Updated on-call station %s (division_id=%s) by %s",
                stations_by_id[entry.id].name, division_id, get_current_user_label(),
            )
        for station_id in deleted_ids:
            logger.info(
                "Deleted on-call station %s (division_id=%s) by %s",
                stations_by_id[station_id].name, division_id, get_current_user_label(),
            )
        return updated

    def delete(self, station_id: int, division_id: UUID):
        station = self.repository.delete(station_id, division_id)
        if not station:
            raise ValueError("On-call station not found")
        logger.info("Deleted on-call station %s (division_id=%s) by %s", station.name, division_id, get_current_user_label())
        return True
