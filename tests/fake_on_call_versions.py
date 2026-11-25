from dataclasses import dataclass, field
from types import SimpleNamespace
from typing import Callable, Optional, TypeVar
from uuid import UUID, uuid4

from app.models.models import OnCallVersionKind

T = TypeVar("T")


@dataclass
class FakeVersionRepository:
    """In-memory stand-in for OnCallSchedulingVersionRepository: one counter per division+month."""
    division_id: UUID = field(default_factory=uuid4)
    versions: list[SimpleNamespace] = field(default_factory=list)
    entities: list[tuple[SimpleNamespace, UUID, OnCallVersionKind]] = field(default_factory=list)

    def division_of(self, unit_id: UUID) -> Optional[UUID]:
        return self.division_id

    def transaction(
        self, division_id: UUID, month: str, created_by: Optional[UUID], body: Callable[[SimpleNamespace], T],
    ) -> T:
        latest = max((v.version for v in self.versions if v.division_id == division_id and v.month == month), default=0)
        row = SimpleNamespace(
            id=len(self.versions) + 1, division_id=division_id, month=month, version=latest + 1, created_by=created_by,
        )
        self.versions.append(row)
        return body(row)

    def record(self, version_row: SimpleNamespace, unit_id: UUID, kind: OnCallVersionKind) -> None:
        self.entities.append((version_row, unit_id, kind))

    def resolve(self, unit_id: UUID, month: str, kind: OnCallVersionKind, at_most: int) -> Optional[int]:
        return max(
            (
                row.version for row, entity_unit_id, entity_kind in self.entities
                if entity_unit_id == unit_id and entity_kind == kind and row.month == month and row.version <= at_most
            ),
            default=None,
        )
