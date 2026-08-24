import contextvars
from typing import Optional, TypedDict

from fastapi import Depends

from app.auth import get_current_user


class CurrentUser(TypedDict, total=False):
    email: str
    name: str
    sub: str


_current_user_var: contextvars.ContextVar[Optional[CurrentUser]] = contextvars.ContextVar(
    "current_user", default=None
)


def get_current_user_label() -> str:
    """Best-effort identifier of the caller, for audit logging.

    Reads the request-scoped user bound by `bind_current_user`. Falls back to
    "unknown" when no user is bound (e.g. this code path is exercised outside
    a request, such as in a script or a test that doesn't go through the
    dependency).
    """
    user = _current_user_var.get()
    if not user:
        return "unknown"
    return user.get("name") or user.get("email") or "unknown"


async def bind_current_user(current_user: dict = Depends(get_current_user)):
    """Route dependency: verifies the Firebase token (via app.auth.get_current_user)
    and stores the decoded claims in a request-scoped ContextVar, so downstream
    service/repository code can read the acting user via get_current_user_label()
    without it being passed through every function call.

    Declared as `async def` (not sync) so FastAPI runs it directly on the
    request's event-loop task instead of a threadpool — required for the
    ContextVar.set() here to actually be visible to the endpoint and everything
    it calls.
    """
    token = _current_user_var.set(current_user)
    try:
        yield current_user
    finally:
        _current_user_var.reset(token)
