"""Finished daily vocab sessions: "done for today" and the streak.

"Today" is the learner's local date. The browser sends its IANA timezone when
a daily session finishes; anything missing or unknown falls back to UTC. Page
renders use the timezone from the learner's latest finished session, since
before their first one there is nothing to be "done" yet.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.extensions import db
from app.models import Level, User, UserDailySession
from app.services.errors import ServiceError

DEFAULT_TIMEZONE = "UTC"


def clean_timezone(name: object) -> str:
    """The IANA timezone name if it is a real one, else UTC."""
    if not isinstance(name, str) or not name or len(name) > 64:
        return DEFAULT_TIMEZONE
    try:
        ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError):
        return DEFAULT_TIMEZONE
    return name


def local_date(tz_name: str, now: datetime | None = None) -> date:
    """The calendar date in tz_name at the instant now (default: current time)."""
    instant = now or datetime.now(timezone.utc)
    return instant.astimezone(ZoneInfo(clean_timezone(tz_name))).date()


def streak_length(done_dates: set[date], today: date) -> int:
    """Consecutive days with a finished daily, ending today or yesterday.

    Not having done today yet does not break the streak: it counts back from
    yesterday until today's session is done. A whole missed day resets it.
    """
    day = today if today in done_dates else today - timedelta(days=1)
    count = 0
    while day in done_dates:
        count += 1
        day -= timedelta(days=1)
    return count


def _latest_timezone(user: User) -> str:
    tz_name = db.session.scalar(
        select(UserDailySession.timezone)
        .where(UserDailySession.user_id == user.id)
        .order_by(UserDailySession.completed_at.desc(), UserDailySession.id.desc())
        .limit(1)
    )
    return clean_timezone(tz_name)


def daily_status(
    user: User, tz_name: str | None = None, now: datetime | None = None
) -> dict:
    """Whether today's daily is done and the current streak in days."""
    tz_name = clean_timezone(tz_name) if tz_name else _latest_timezone(user)
    today = local_date(tz_name, now)
    done_dates = set(
        db.session.scalars(
            select(UserDailySession.local_date).where(
                UserDailySession.user_id == user.id
            )
        ).all()
    )
    return {
        "done_today": today in done_dates,
        "streak": streak_length(done_dates, today),
        "today": today.isoformat(),
    }


def record_daily_done(
    user: User, level_id: str, tz_name: object, now: datetime | None = None
) -> dict:
    """Store that the learner finished a daily session today (idempotent)."""
    if db.session.get(Level, level_id) is None:
        raise ServiceError("Level not found", 404)
    tz_clean = clean_timezone(tz_name)
    today = local_date(tz_clean, now)
    existing = db.session.scalar(
        select(UserDailySession).where(
            UserDailySession.user_id == user.id,
            UserDailySession.local_date == today,
        )
    )
    if existing is None:
        db.session.add(
            UserDailySession(
                user_id=user.id,
                level_id=level_id,
                local_date=today,
                timezone=tz_clean,
                completed_at=now or datetime.now(timezone.utc),
            )
        )
        try:
            db.session.commit()
        except IntegrityError:
            # A second tab finished the same day at the same moment.
            db.session.rollback()
    else:
        # Keep the latest timezone so later page renders use it.
        existing.timezone = tz_clean
        existing.completed_at = now or datetime.now(timezone.utc)
        db.session.commit()
    return daily_status(user, tz_clean, now)
