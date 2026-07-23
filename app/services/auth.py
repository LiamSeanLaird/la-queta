import re

from flask import session
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.extensions import db
from app.models import User
from app.services.errors import ServiceError

HANDLE_RE = re.compile(r"^[a-zA-Z0-9_-]{3,24}$")
SESSION_USER_KEY = "session_user"


class AuthError(ServiceError):
    pass


def validate_handle(handle: object) -> str:
    if not isinstance(handle, str):
        raise AuthError("Handle is required", 400)
    cleaned = handle.strip()
    if not cleaned:
        raise AuthError("Handle is required", 400)
    if not HANDLE_RE.fullmatch(cleaned):
        raise AuthError(
            "Handle must be 3–24 characters: letters, numbers, _ or -",
            400,
        )
    return cleaned


def user_to_dict(user: User) -> dict:
    return {
        "id": user.id,
        "handle": user.handle,
        "current_level_id": user.current_level_id,
    }


def register_user(handle: object) -> User:
    cleaned = validate_handle(handle)
    existing = db.session.scalar(select(User).where(User.handle == cleaned))
    if existing is not None:
        raise AuthError("Handle already taken", 409)

    user = User(handle=cleaned)
    db.session.add(user)
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        raise AuthError("Handle already taken", 409) from None
    return user


def get_user_by_id(user_id: int) -> User | None:
    return db.session.get(User, user_id)


def login_user(user: User) -> None:
    session.clear()
    session[SESSION_USER_KEY] = user.id
    session.permanent = True


def current_user() -> User | None:
    user_id = session.get(SESSION_USER_KEY)
    if not isinstance(user_id, int):
        return None
    return get_user_by_id(user_id)


def require_user() -> User:
    user = current_user()
    if user is None:
        raise AuthError("Not authenticated", 401)
    return user
