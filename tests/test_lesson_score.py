"""Test scores: best first-try count per lesson, stars, and the migration."""

from __future__ import annotations

import re
from datetime import datetime

import pytest
import sqlalchemy as sa
from flask_migrate import downgrade, upgrade
from sqlalchemy import select

from app.extensions import db
from app.models import Lesson, UserLessonProgress
from app.services.lessons import lesson_stars
from app.services.seed import seed_all

LESSON_ID = "noun-gender"


@pytest.fixture
def seeded(migrated_app):
    with migrated_app.app_context():
        seed_all()
        total = len(db.session.get(Lesson, LESSON_ID).practice_json)
    return total


def _register(client, handle="Scorer"):
    response = client.post(
        "/api/auth/register",
        json={
            "handle": handle,
            "email": f"{handle.lower()}@example.com",
            "password": "password1",
        },
    )
    assert response.status_code == 201


def _complete(client, total, **extra):
    return client.post(
        f"/api/lessons/{LESSON_ID}/complete",
        json={"exercises_correct": total, "exercises_total": total, **extra},
    )


@pytest.mark.parametrize(
    ("completed", "best", "total", "stars"),
    [
        (False, None, 14, 0),
        (False, 14, 14, 0),
        (True, None, 14, 1),
        (True, 14, 14, 3),
        (True, 13, 14, 2),
        (True, 11, 14, 2),  # 78.6%
        (True, 10, 14, 1),  # 71.4%
        (True, 3, 4, 2),  # exactly 75%
        (True, 2, 4, 1),
        (True, 0, 14, 1),
    ],
)
def test_star_thresholds(completed, best, total, stars):
    assert lesson_stars(completed, best, total) == stars


def test_score_is_saved_and_shown_as_stars(seeded, migrated_client):
    total = seeded
    _register(migrated_client)
    body = _complete(migrated_client, total, first_try_correct=total - 1).get_json()
    assert body["completed"] is True
    assert body["best_first_try"] == total - 1
    assert body["stars"] == 2

    listed = migrated_client.get("/api/levels/a1/lessons").get_json()["lessons"]
    stars = {row["id"]: row["stars"] for row in listed}
    assert stars[LESSON_ID] == 2
    assert set(stars.values()) - {2} == {0}


def test_worse_retake_never_lowers_the_best(seeded, migrated_client, migrated_app):
    total = seeded
    _register(migrated_client)
    assert _complete(migrated_client, total, first_try_correct=5).status_code == 200
    with migrated_app.app_context():
        first_completed_at = db.session.scalar(select(UserLessonProgress)).completed_at

    better = _complete(migrated_client, total, first_try_correct=total).get_json()
    assert (better["best_first_try"], better["stars"]) == (total, 3)

    worse = _complete(migrated_client, total, first_try_correct=2).get_json()
    assert (worse["best_first_try"], worse["stars"]) == (total, 3)

    with migrated_app.app_context():
        row = db.session.scalar(select(UserLessonProgress))
        # A retake keeps the date the lesson was first completed.
        assert row.completed_at == first_completed_at


def test_older_clients_without_a_score_still_complete(seeded, migrated_client):
    total = seeded
    _register(migrated_client)
    body = _complete(migrated_client, total).get_json()
    assert body["completed"] is True
    assert body["best_first_try"] is None
    assert body["stars"] == 1

    # A later scored retake records a best; an unscored one keeps it.
    _complete(migrated_client, total, first_try_correct=total - 4)
    body = _complete(migrated_client, total).get_json()
    assert body["best_first_try"] == total - 4


@pytest.mark.parametrize("bad", [-1, "+1", "3", 1.5, True, [3]])
def test_invalid_first_try_scores_are_rejected(seeded, migrated_client, bad):
    total = seeded
    _register(migrated_client)
    if bad == "+1":
        bad = total + 1
    response = _complete(migrated_client, total, first_try_correct=bad)
    assert response.status_code == 400, bad
    detail = migrated_client.get(f"/api/lessons/{LESSON_ID}").get_json()
    assert detail["completed"] is False
    assert detail["stars"] == 0


def test_saving_a_score_needs_an_account(seeded, migrated_client):
    response = _complete(migrated_client, seeded, first_try_correct=seeded)
    assert response.status_code == 401


def test_migration_keeps_production_rows_and_leaves_score_empty(migrated_app):
    """Rows completed before scoring keep every value and show 1 star."""
    with migrated_app.app_context():
        seed_all()
        downgrade(revision="d1e2f3a4b5c6")
        conn = db.session.connection()
        conn.execute(
            sa.text(
                "INSERT INTO users (handle, email, password_hash) "
                "VALUES ('prod', 'prod@example.com', 'x')"
            )
        )
        user_id = conn.execute(
            sa.text("SELECT id FROM users WHERE handle = 'prod'")
        ).scalar()
        rows = [
            ("noun-gender", 1, 14, 14, "2026-03-01 10:00:00"),
            ("definite-articles", 0, 0, 0, None),
        ]
        for lesson_id, completed, correct, total, completed_at in rows:
            conn.execute(
                sa.text(
                    "INSERT INTO user_lesson_progress (user_id, lesson_id, "
                    "completed, exercises_correct, exercises_total, completed_at) "
                    "VALUES (:u, :l, :c, :ec, :et, :at)"
                ),
                {
                    "u": user_id,
                    "l": lesson_id,
                    "c": completed,
                    "ec": correct,
                    "et": total,
                    "at": completed_at,
                },
            )
        db.session.commit()

        upgrade()
        db.session.expire_all()

        progress = {
            row.lesson_id: row
            for row in db.session.scalars(
                select(UserLessonProgress).where(UserLessonProgress.user_id == user_id)
            )
        }
        done = progress["noun-gender"]
        assert (done.completed, done.exercises_correct, done.exercises_total) == (
            True,
            14,
            14,
        )
        assert done.completed_at.replace(tzinfo=None) == datetime(2026, 3, 1, 10)
        assert done.best_first_try is None
        not_done = progress["definite-articles"]
        assert (not_done.completed, not_done.completed_at) == (False, None)
        assert not_done.best_first_try is None

        lesson = db.session.get(Lesson, "noun-gender")
        assert lesson_stars(done.completed, done.best_first_try, 14) == 1
        assert len(lesson.practice_json) == 14


def _row_status(html: str, lesson_id: str) -> str:
    """The status a lesson list row shows: its stars label, or 'Todo'."""
    row = re.search(
        rf'<a class="list-row" href="/lessons/{lesson_id}">(.*?)</a>', html, re.S
    )
    assert row, f"no row for {lesson_id}"
    label = re.search(r'aria-label="(Done, \d of 3 stars)"', row.group(1))
    if label:
        return label.group(1)
    return "Todo" if "badge--todo" in row.group(1) else ""


def test_best_stars_show_on_level_lessons_and_lesson_pages(seeded, migrated_client):
    total = seeded
    _register(migrated_client)
    assert _complete(migrated_client, total, first_try_correct=total - 1).status_code == 200
    # A worse retake keeps the best score everywhere it is shown.
    assert _complete(migrated_client, total, first_try_correct=0).status_code == 200

    level = migrated_client.get("/levels/a1").get_data(as_text=True)
    assert _row_status(level, LESSON_ID) == "Done, 2 of 3 stars"
    assert _row_status(level, "definite-articles") == "Todo"

    lessons = migrated_client.get("/lessons").get_data(as_text=True)
    assert _row_status(lessons, LESSON_ID) == "Done, 2 of 3 stars"
    assert _row_status(lessons, "definite-articles") == ""

    page = migrated_client.get(f"/lessons/{LESSON_ID}").get_data(as_text=True)
    assert 'id="lesson-best"' in page
    assert 'aria-label="Done, 2 of 3 stars"' in page
    assert f"{total - 1} of {total} right first time" in page

    other = migrated_client.get("/lessons/definite-articles").get_data(as_text=True)
    assert 'id="lesson-best"' not in other


def test_lesson_header_without_a_score_shows_one_star_only(seeded, migrated_client):
    # A completion from an older client (or production before scores) has no
    # first-try count: the header shows 1 star and no "right first time" line.
    total = seeded
    _register(migrated_client)
    assert _complete(migrated_client, total).status_code == 200
    page = migrated_client.get(f"/lessons/{LESSON_ID}").get_data(as_text=True)
    assert 'aria-label="Done, 1 of 3 stars"' in page
    assert "right first time</span>" not in page


def test_logged_out_lesson_page_has_no_best_score(seeded, migrated_client):
    page = migrated_client.get(f"/lessons/{LESSON_ID}").get_data(as_text=True)
    assert 'id="lesson-best"' not in page
    assert "of 3 stars" not in page


def _star_icons(html: str, label: str) -> list[bool]:
    """Earned flags of the three star icons inside the element with this label."""
    block = re.search(rf'aria-label="{label}">(.*?)</(?:span|p)>', html, re.S)
    assert block, f"no stars labelled {label!r}"
    icons = re.findall(r'<svg class="([^"]*)"', block.group(1))
    return ["is-earned" in classes for classes in icons]


def test_stars_render_as_three_icons_earned_ones_first(seeded, migrated_client):
    # Earned and empty stars are the same icon, told apart by is-earned (filled
    # gold) or its absence (a hollow outline), so a row always shows three.
    total = seeded
    _register(migrated_client)
    assert _complete(migrated_client, total, first_try_correct=total - 1).status_code == 200
    page = migrated_client.get(f"/lessons/{LESSON_ID}").get_data(as_text=True)
    assert _star_icons(page, "Done, 2 of 3 stars") == [True, True, False]


def test_done_panel_has_three_empty_stars_for_the_script_to_fill(seeded, migrated_client):
    page = migrated_client.get(f"/lessons/{LESSON_ID}?tab=test").get_data(as_text=True)
    block = re.search(r'id="test-score-stars"[^>]*>(.*?)</p>', page, re.S)
    assert block
    icons = re.findall(r'<svg class="([^"]*)"', block.group(1))
    assert icons == ["test-score__star"] * 3
