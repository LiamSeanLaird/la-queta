"""Daily vocab "done for today" and streak, on the learner's local date."""

from __future__ import annotations

from datetime import date, datetime, timezone

import pytest

from app.extensions import db
from app.models import User, UserDailySession
from app.services.daily import (
    clean_timezone,
    daily_status,
    local_date,
    record_daily_done,
    streak_length,
)
from app.services.seed import seed_all


def _register(client, handle: str = "streaker"):
    response = client.post(
        "/api/auth/register",
        json={"handle": handle, "email": f"{handle}@example.com", "password": "password1"},
    )
    assert response.status_code == 201
    return response.get_json()


def _utc(*args) -> datetime:
    return datetime(*args, tzinfo=timezone.utc)


# ── Pure date logic ──────────────────────────────────────


@pytest.mark.parametrize(
    "name, expected",
    [
        ("Europe/Madrid", "Europe/Madrid"),
        ("America/Los_Angeles", "America/Los_Angeles"),
        ("UTC", "UTC"),
        ("Not/AZone", "UTC"),
        ("../../etc/passwd", "UTC"),
        ("", "UTC"),
        (None, "UTC"),
        (42, "UTC"),
        ("x" * 100, "UTC"),
    ],
)
def test_clean_timezone(name, expected):
    assert clean_timezone(name) == expected


def test_local_date_just_after_midnight_in_two_timezones():
    # 23:30 UTC on 9 March is 00:30 on 10 March in Madrid (UTC+1)
    # but still 15:30 on 9 March in Los Angeles (UTC-8).
    instant = _utc(2026, 3, 9, 23, 30)
    assert local_date("Europe/Madrid", instant) == date(2026, 3, 10)
    assert local_date("America/Los_Angeles", instant) == date(2026, 3, 9)
    assert local_date("UTC", instant) == date(2026, 3, 9)
    assert local_date("Bogus/Zone", instant) == date(2026, 3, 9)


def test_streak_counts_consecutive_days_ending_today():
    days = {date(2026, 3, 8), date(2026, 3, 9), date(2026, 3, 10)}
    assert streak_length(days, date(2026, 3, 10)) == 3


def test_today_not_done_keeps_yesterdays_streak():
    days = {date(2026, 3, 8), date(2026, 3, 9)}
    assert streak_length(days, date(2026, 3, 10)) == 2


def test_missed_day_resets_streak():
    days = {date(2026, 3, 7), date(2026, 3, 8)}
    assert streak_length(days, date(2026, 3, 10)) == 0
    days.add(date(2026, 3, 10))
    assert streak_length(days, date(2026, 3, 10)) == 1


def test_streak_across_month_end():
    days = {date(2026, 2, 27), date(2026, 2, 28), date(2026, 3, 1)}
    assert streak_length(days, date(2026, 3, 1)) == 3


def test_no_sessions_no_streak():
    assert streak_length(set(), date(2026, 3, 10)) == 0


# ── Recording sessions ───────────────────────────────────


@pytest.fixture
def learner(migrated_app, migrated_client):
    with migrated_app.app_context():
        seed_all()
    body = _register(migrated_client)
    with migrated_app.app_context():
        yield db.session.get(User, body["id"])


def test_record_uses_local_date_and_is_idempotent(learner):
    # Just after midnight in Madrid: the session belongs to the new day there.
    status = record_daily_done(learner, "a1", "Europe/Madrid", _utc(2026, 3, 9, 23, 30))
    assert status == {"done_today": True, "streak": 1, "today": "2026-03-10"}
    record_daily_done(learner, "a1", "Europe/Madrid", _utc(2026, 3, 10, 8, 0))
    rows = db.session.query(UserDailySession).filter_by(user_id=learner.id).all()
    assert [row.local_date for row in rows] == [date(2026, 3, 10)]


def test_same_instant_is_different_days_in_two_timezones(learner):
    record_daily_done(learner, "a1", "America/Los_Angeles", _utc(2026, 3, 9, 23, 30))
    row = db.session.query(UserDailySession).filter_by(user_id=learner.id).one()
    assert row.local_date == date(2026, 3, 9)
    assert row.timezone == "America/Los_Angeles"
    # In Madrid that same instant is already the 10th, so today is not done
    # there, but yesterday's session keeps the streak alive.
    madrid = daily_status(learner, "Europe/Madrid", _utc(2026, 3, 9, 23, 30))
    assert madrid == {"done_today": False, "streak": 1, "today": "2026-03-10"}


def test_status_uses_timezone_of_latest_session(learner):
    record_daily_done(learner, "a1", "Europe/Madrid", _utc(2026, 3, 9, 9, 0))
    # 23:30 UTC on the 9th is after midnight in Madrid: a new day, not done yet.
    assert daily_status(learner, now=_utc(2026, 3, 9, 22, 0))["done_today"] is True
    later = daily_status(learner, now=_utc(2026, 3, 9, 23, 30))
    assert later == {"done_today": False, "streak": 1, "today": "2026-03-10"}


def test_streak_builds_and_resets(learner):
    tz = "Europe/Madrid"
    for day in (8, 9, 10):
        record_daily_done(learner, "a1", tz, _utc(2026, 3, day, 18, 0))
    assert daily_status(learner, tz, _utc(2026, 3, 10, 19, 0))["streak"] == 3
    assert daily_status(learner, tz, _utc(2026, 3, 11, 19, 0)) == {
        "done_today": False,
        "streak": 3,
        "today": "2026-03-11",
    }
    # Skip the 11th entirely.
    assert daily_status(learner, tz, _utc(2026, 3, 12, 19, 0))["streak"] == 0
    status = record_daily_done(learner, "a1", tz, _utc(2026, 3, 12, 19, 0))
    assert status["streak"] == 1


# ── HTTP ─────────────────────────────────────────────────


def test_complete_endpoint_requires_login(migrated_app, migrated_client):
    response = migrated_client.post("/api/levels/a1/daily/complete", json={})
    assert response.status_code == 401


def test_complete_endpoint_unknown_level(migrated_app, migrated_client):
    with migrated_app.app_context():
        seed_all()
    _register(migrated_client)
    response = migrated_client.post("/api/levels/zz/daily/complete", json={})
    assert response.status_code == 404


def test_complete_endpoint_falls_back_to_utc(migrated_app, migrated_client):
    with migrated_app.app_context():
        seed_all()
    _register(migrated_client)
    response = migrated_client.post(
        "/api/levels/a1/daily/complete", json={"timezone": "Mars/Olympus"}
    )
    assert response.status_code == 200
    body = response.get_json()
    assert body["done_today"] is True
    assert body["streak"] == 1
    assert body["today"] == datetime.now(timezone.utc).date().isoformat()


def test_levels_page_shows_done_state_and_streak(migrated_app, migrated_client):
    with migrated_app.app_context():
        seed_all()
    _register(migrated_client)
    before = migrated_client.get("/levels").get_data(as_text=True)
    assert 'class="btn btn--secondary btn--block daily-cta__btn" href="/levels/a1/daily">Daily vocab</a>' in before
    assert "done for today" not in before
    assert "daily-cta__streak" not in before

    migrated_client.post("/api/levels/a1/daily/complete", json={"timezone": "UTC"})
    after = migrated_client.get("/levels").get_data(as_text=True)
    assert "Daily vocab - done for today" in after
    assert 'href="/levels/a1/daily"' in after
    assert "1-day streak" in after
    assert "keep it" not in after


def test_daily_page_carries_complete_url_and_deck_study_does_not(
    migrated_app, migrated_client
):
    with migrated_app.app_context():
        seed_all()
    _register(migrated_client)
    daily = migrated_client.get("/levels/a1/daily").get_data(as_text=True)
    assert 'data-complete-url="/api/levels/a1/daily/complete"' in daily
    deck = migrated_client.get("/decks/starter/study").get_data(as_text=True)
    assert "data-complete-url" not in deck
