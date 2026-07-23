from sqlalchemy import select

from app.extensions import db
from app.models import Level, User
from app.services.errors import ServiceError
from app.services.progress import level_completeness_pct

# Only A1 has content today; A2/B1 are hub placeholders.
OPEN_LEVEL_IDS = frozenset({"a1"})


def level_is_open(level_id: str) -> bool:
    return level_id in OPEN_LEVEL_IDS


def list_levels_for_user(user: User) -> list[dict]:
    levels = db.session.scalars(select(Level).order_by(Level.sort_order)).all()
    return [
        {
            "id": level.id,
            "code": level.code,
            "title": level.title,
            "sort_order": level.sort_order,
            "complete_pct": level_completeness_pct(user.id, level.id),
            "is_current": user.current_level_id == level.id,
            "available": level_is_open(level.id),
        }
        for level in levels
    ]


def select_level(user: User, level_id: str) -> User:
    level = db.session.get(Level, level_id)
    if level is None:
        raise ServiceError("Level not found", 404)
    if not level_is_open(level.id):
        raise ServiceError("Level not available yet", 400)
    user.current_level_id = level.id
    db.session.commit()
    return user
