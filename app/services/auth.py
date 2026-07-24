import re

from flask import session
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from werkzeug.security import check_password_hash, generate_password_hash

from app.extensions import db
from app.models import User
from app.services.errors import ServiceError

# Display name stored in `handle`
NAME_RE = re.compile(
    r"^[a-zA-ZÀ-ÿ0-9](?:[a-zA-ZÀ-ÿ0-9 '\-]{0,38}[a-zA-ZÀ-ÿ0-9])?$"
)
EMAIL_RE = re.compile(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$")
MAX_EMAIL_LEN = 254
MIN_PASSWORD_LEN = 6
MAX_PASSWORD_LEN = 128
SESSION_USER_KEY = "session_user"


class AuthError(ServiceError):
    pass


def validate_handle(handle: object) -> str:
    if not isinstance(handle, str):
        raise AuthError("Name is required", 400)
    cleaned = " ".join(handle.strip().split())
    if not cleaned:
        raise AuthError("Name is required", 400)
    if len(cleaned) < 2 or len(cleaned) > 40:
        raise AuthError("Name must be 2–40 characters", 400)
    if not NAME_RE.fullmatch(cleaned):
        raise AuthError(
            "Name can use letters, numbers, spaces, hyphens, and apostrophes",
            400,
        )
    return cleaned


def validate_email(email: object) -> str:
    if not isinstance(email, str):
        raise AuthError("Email is required", 400)
    cleaned = email.strip().lower()
    if not cleaned:
        raise AuthError("Email is required", 400)
    if len(cleaned) > MAX_EMAIL_LEN:
        raise AuthError("Email is too long", 400)
    if not EMAIL_RE.fullmatch(cleaned):
        raise AuthError("Enter a valid email address", 400)
    return cleaned


def validate_password(password: object) -> str:
    if not isinstance(password, str):
        raise AuthError("Password is required", 400)
    if len(password) < MIN_PASSWORD_LEN:
        raise AuthError(f"Password must be at least {MIN_PASSWORD_LEN} characters", 400)
    if len(password) > MAX_PASSWORD_LEN:
        raise AuthError("Password is too long", 400)
    return password


def user_to_dict(user: User) -> dict:
    return {
        "id": user.id,
        "handle": user.handle,
        "email": user.email,
        "current_level_id": user.current_level_id,
    }


def register_user(handle: object, email: object, password: object) -> User:
    cleaned_handle = validate_handle(handle)
    cleaned_email = validate_email(email)
    cleaned_password = validate_password(password)

    if db.session.scalar(
        select(User).where(func.lower(User.handle) == cleaned_handle.lower())
    ):
        raise AuthError("That name is already taken", 409)
    if db.session.scalar(select(User).where(User.email == cleaned_email)):
        raise AuthError("Email already used", 409)

    user = User(
        handle=cleaned_handle,
        email=cleaned_email,
        password_hash=generate_password_hash(cleaned_password),
    )
    db.session.add(user)
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        if db.session.scalar(select(User).where(User.email == cleaned_email)):
            raise AuthError("Email already used", 409) from None
        raise AuthError("That name is already taken", 409) from None
    return user


def authenticate_user(email: object, password: object) -> User:
    """Login by email + password. Same error for unknown email or bad password."""
    cleaned_email = validate_email(email)
    if not isinstance(password, str) or not password:
        raise AuthError("Invalid email or password", 401)

    user = db.session.scalar(select(User).where(User.email == cleaned_email))
    if user is None or not check_password_hash(user.password_hash, password):
        raise AuthError("Invalid email or password", 401)
    return user


def get_user_by_id(user_id: int) -> User | None:
    return db.session.get(User, user_id)


def login_user(user: User) -> None:
    session.clear()
    session[SESSION_USER_KEY] = user.id
    session.permanent = True


def logout_user() -> None:
    session.clear()


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


def update_user_profile(user: User, handle: object, email: object) -> User:
    cleaned_handle = validate_handle(handle)
    cleaned_email = validate_email(email)

    other_handle = db.session.scalar(
        select(User).where(
            func.lower(User.handle) == cleaned_handle.lower(),
            User.id != user.id,
        )
    )
    if other_handle is not None:
        raise AuthError("That name is already taken", 409)

    other_email = db.session.scalar(
        select(User).where(User.email == cleaned_email, User.id != user.id)
    )
    if other_email is not None:
        raise AuthError("Email already used", 409)

    user.handle = cleaned_handle
    user.email = cleaned_email
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        raise AuthError("Could not update profile", 409) from None
    return user
