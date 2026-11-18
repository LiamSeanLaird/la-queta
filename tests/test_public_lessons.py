"""Lesson pages are public: logged-out visitors can read and practise every lesson."""

import json
import re
from html import unescape

from sqlalchemy import select

from app.extensions import db
from app.models import Lesson
from app.services.lessons import get_lesson, list_lessons_for_level
from app.services.progress import lesson_next_steps
from app.services.seed import seed_all


def _lessons(app):
    with app.app_context():
        seed_all()
        rows = db.session.scalars(
            select(Lesson).order_by(Lesson.sort_order, Lesson.id)
        ).all()
        return [
            {
                "id": row.id,
                "title": row.title,
                "first_text": next(
                    s["content"] for s in row.sections_json if s["type"] == "text"
                ),
                "practice": row.practice_json,
            }
            for row in rows
        ]


def _register(client):
    response = client.post(
        "/api/auth/register",
        json={"handle": "Visitor", "email": "visitor@example.com", "password": "password1"},
    )
    assert response.status_code == 201


def _text(html: bytes) -> str:
    return unescape(re.sub(r"<[^>]+>", "", html.decode()))


def test_every_lesson_renders_logged_out(migrated_app, migrated_client):
    lessons = _lessons(migrated_app)
    assert len(lessons) == 20
    for lesson in lessons:
        response = migrated_client.get(f"/lessons/{lesson['id']}")
        assert response.status_code == 200, lesson["id"]
        text = _text(response.data)
        assert lesson["title"] in text
        # The Learn tab's opening paragraph is in the HTML a crawler sees.
        assert lesson["first_text"][:40] in text, lesson["id"]


def test_practice_tab_renders_logged_out(migrated_app, migrated_client):
    lesson = _lessons(migrated_app)[0]
    response = migrated_client.get(f"/lessons/{lesson['id']}?tab=practice")
    assert response.status_code == 200
    html = response.data.decode()
    assert "js/practice.js" in html
    assert 'data-logged-in="false"' in html
    data = re.search(
        r'<script type="application/json" id="practice-data">(.*?)</script>', html, re.S
    )
    assert json.loads(data.group(1)) == lesson["practice"]
    # The completion step asks for an account instead of claiming it was saved.
    assert "Create a free account to save this lesson and keep going." in html
    assert "Lesson complete - well done." not in html
    assert 'href="/signup">Create a free account</a>' in html
    assert 'href="/signin">Sign in</a>' in html


def test_logged_out_topbar_offers_sign_in(migrated_app, migrated_client):
    lesson = _lessons(migrated_app)[0]
    html = migrated_client.get(f"/lessons/{lesson['id']}").data.decode()
    assert 'class="btn btn--secondary topbar__signin" href="/signin"' in html
    assert 'id="profile-open"' not in html
    assert 'id="profile-dialog"' not in html
    assert "profile-logout" not in html
    # Back and brand go to the public home page, not the logged-in hub.
    assert 'class="topbar__back" href="/"' in html
    assert 'class="brand__link" href="/"' in html


def test_logged_out_completion_post_is_401(migrated_app, migrated_client):
    lesson = _lessons(migrated_app)[0]
    total = len(lesson["practice"])
    response = migrated_client.post(
        f"/api/lessons/{lesson['id']}/complete",
        json={"exercises_correct": total, "exercises_total": total},
    )
    assert response.status_code == 401


def test_unknown_lesson_logged_out_goes_home(migrated_app, migrated_client):
    _lessons(migrated_app)
    response = migrated_client.get("/lessons/no-such-lesson")
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/")


def test_logged_in_lesson_page_unchanged(migrated_app, migrated_client):
    lesson = _lessons(migrated_app)[0]
    _register(migrated_client)
    html = migrated_client.get(f"/lessons/{lesson['id']}?tab=practice").data.decode()
    assert 'data-logged-in="true"' in html
    assert "Lesson complete - well done." in html
    assert "topbar__signin" not in html
    assert 'id="profile-open"' in html
    assert 'class="topbar__back" href="/levels/a1"' in html


def test_services_logged_out_path(migrated_app):
    lessons = _lessons(migrated_app)
    with migrated_app.app_context():
        listed = list_lessons_for_level(None, "a1")
        assert [row["id"] for row in listed] == [row["id"] for row in lessons]
        assert not any(row["completed"] for row in listed)

        detail = get_lesson(None, lessons[0]["id"])
        assert detail["completed"] is False
        assert detail["exercises_correct"] == 0

        steps = lesson_next_steps(None, lessons[0]["id"])
        assert steps["deck"] is None
        assert steps["next_lesson"]["id"] == lessons[1]["id"]
        # No wrap-round for a visitor: the last lesson has no next lesson.
        assert lesson_next_steps(None, lessons[-1]["id"])["next_lesson"] is None


def test_sign_up_after_practice_saves_the_lesson(migrated_app, migrated_client):
    """The server half of the flow gate.js runs after a logged-out Practice."""
    lesson = _lessons(migrated_app)[0]
    total = len(lesson["practice"])
    _register(migrated_client)
    response = migrated_client.post(
        f"/api/lessons/{lesson['id']}/complete",
        json={"exercises_correct": total, "exercises_total": total},
    )
    assert response.status_code == 200
    assert response.get_json()["completed"] is True

    html = migrated_client.get(f"/lessons/{lesson['id']}?saved=1").data.decode()
    assert 'id="lesson-saved"' in html
    assert "Saved to your account." in html
    listed = migrated_client.get("/api/levels/a1/lessons").get_json()["lessons"]
    assert [row["id"] for row in listed if row["completed"]] == [lesson["id"]]


def test_carried_completion_uses_the_same_validation(migrated_app, migrated_client):
    lesson = _lessons(migrated_app)[0]
    total = len(lesson["practice"])
    _register(migrated_client)
    for payload in (
        {"exercises_correct": total - 1, "exercises_total": total},
        {"exercises_correct": 1, "exercises_total": 1},
        {"exercises_correct": "9", "exercises_total": "9"},
    ):
        response = migrated_client.post(f"/api/lessons/{lesson['id']}/complete", json=payload)
        assert response.status_code == 400, payload
    html = migrated_client.get(f"/lessons/{lesson['id']}?saved=1").data.decode()
    # Not completed, so ?saved=1 does not claim anything was saved.
    assert 'id="lesson-saved"' not in html


def test_saved_note_needs_an_account(migrated_app, migrated_client):
    lesson = _lessons(migrated_app)[0]
    html = migrated_client.get(f"/lessons/{lesson['id']}?saved=1").data.decode()
    assert 'id="lesson-saved"' not in html

