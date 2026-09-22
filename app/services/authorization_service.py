import logging
from typing import Optional
from uuid import UUID

from app.services.unit_service import UnitService
from app.services.division_service import DivisionService
from app.services.user_service import UserService
from app.schemas.schemas import UserRole, UserResponse

logger = logging.getLogger(__name__)

# "admins + owners" per the constraints feature's access rules.
ADMIN_ROLES = {UserRole.owner, UserRole.division_admin, UserRole.unit_admin}


class AuthorizationError(Exception):
    def __init__(self, message: str = "You do not have access to this resource"):
        self.message = message
        super().__init__(message)


class AuthorizationService:
    """Scope rules (per role, for the constraints feature):
    - owner: any unit/account within their own account.
    - division_admin: any unit within their own division.
    - unit_admin: only their own unit.
    - user (regular staff): only their own unit for write-capable/self-serve
      actions (`authorize_unit`) — and, separately, enforced by the calling
      service, not here, only their own submission. For read-only "view the
      calendar" endpoints (`authorize_unit_view`), any unit within their own
      division, same as division_admin.
    """

    def __init__(self, user_service: UserService, unit_service: UnitService, division_service: DivisionService):
        self.user_service = user_service
        self.unit_service = unit_service
        self.division_service = division_service
        self._account_id_cache: dict[UUID, Optional[UUID]] = {}

    def get_logged_in_user_or_raise(self, current_user: dict) -> UserResponse:
        user = self.user_service.get_logged_in_user(current_user)
        if not user:
            raise AuthorizationError("Logged-in user not found")
        return user

    def require_admin_role(self, user: UserResponse) -> None:
        if user.role not in ADMIN_ROLES:
            raise AuthorizationError("This action requires an admin or owner role")

    def is_admin(self, user: UserResponse) -> bool:
        return user.role in ADMIN_ROLES

    def get_account_id_or_raise(self, user: UserResponse) -> UUID:
        account_id = self.user_account_id(user)
        if not account_id:
            raise AuthorizationError("Could not determine your account")
        return account_id

    def account_id_for_unit(self, unit_id: UUID) -> Optional[UUID]:
        unit = self.unit_service.get_unit_details(unit_id)
        return unit["account_id"] if unit else None

    def account_id_for_division(self, division_id: UUID) -> Optional[UUID]:
        division = self.division_service.get_division_details(division_id)
        return division["account_id"] if division else None

    def user_account_id(self, user: UserResponse) -> Optional[UUID]:
        if user.id in self._account_id_cache:
            return self._account_id_cache[user.id]
        if user.division_id:
            result = self.account_id_for_division(user.division_id)
        elif user.unit_id:
            result = self.account_id_for_unit(user.unit_id)
        else:
            result = None
        self._account_id_cache[user.id] = result
        return result

    def user_division_id(self, user: UserResponse) -> Optional[UUID]:
        if user.division_id:
            return user.division_id
        if user.unit_id:
            unit = self.unit_service.get_unit_details(user.unit_id)
            return unit["division_id"] if unit else None
        return None

    def authorize_unit(self, user: UserResponse, unit_id: UUID) -> None:
        """Verifies `user` is allowed to act on `unit_id`, per their role's
        scope. This is the scope for write-capable and self-serve actions —
        a plain `user` is restricted to their own unit here even though
        `authorize_unit_view` lets them read any unit in their division."""
        if user.role in (UserRole.unit_admin, UserRole.user):
            if unit_id != user.unit_id:
                raise AuthorizationError("You can only access your own unit")
            return
        if user.role == UserRole.division_admin:
            unit = self.unit_service.get_unit_details(unit_id)
            if not unit or unit["division_id"] != user.division_id:
                raise AuthorizationError("This unit is not in your division")
            return
        if user.role == UserRole.owner:
            target_account_id = self.account_id_for_unit(unit_id)
            if not target_account_id or target_account_id != self.user_account_id(user):
                raise AuthorizationError("This unit is not in your account")
            return
        raise AuthorizationError("Unrecognized role")

    def authorize_unit_view(self, user: UserResponse, unit_id: UUID) -> None:
        """Like `authorize_unit`, but for the read-only "view the calendar"
        endpoints (GET /constraints, /history, /submission-metadata) where a
        plain `user` may see any unit in their own division — not just their
        own unit — same scope a division_admin already gets. Every other
        role's scope is unchanged from `authorize_unit`."""
        if user.role != UserRole.user:
            self.authorize_unit(user, unit_id)
            return
        unit = self.unit_service.get_unit_details(unit_id)
        target_division_id = unit["division_id"] if unit else None
        if not target_division_id or target_division_id != self.user_division_id(user):
            raise AuthorizationError("This unit is not in your division")

    def authorize_division(self, user: UserResponse, division_id: UUID) -> None:
        """Division-scoped equivalent of authorize_unit, for endpoints keyed
        by division_id rather than unit_id (e.g on_call_stations)."""
        if user.role in (UserRole.unit_admin, UserRole.user):
            if division_id != self.user_division_id(user):
                raise AuthorizationError("This division is not yours")
            return
        if user.role == UserRole.division_admin:
            if division_id != user.division_id:
                raise AuthorizationError("This division is not yours")
            return
        if user.role == UserRole.owner:
            target_account_id = self.account_id_for_division(division_id)
            if not target_account_id or target_account_id != self.user_account_id(user):
                raise AuthorizationError("This division is not in your account")
            return
        raise AuthorizationError("Unrecognized role")

    def authorize_account(self, user: UserResponse, account_id: UUID) -> None:
        """Every role's own account is derived the same way — no role
        branching needed here (unlike `authorize_unit`, where higher roles
        get access to more than just their own single unit)."""
        if account_id != self.user_account_id(user):
            raise AuthorizationError("This account is not yours")
