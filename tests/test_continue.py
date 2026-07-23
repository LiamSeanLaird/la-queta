"""Phase 6 — continue CTA / next incomplete lesson."""

from __future__ import annotations

from app.extensions import db
from app.models import User
from app.services.progress import continue_target, next_incomplete_lesson
from app.services.seed import seed_all


def _register(client, handle: str = "continuer"):
    slug = "".join(handle.lower().split())
    response = client.post(
        "/api/auth/register",
        json={
            "handle": handle,
            "email": f"{slug}@example.com",
            "password": "password1",
        },
    )
    assert response.status_code == 201
    return response.get_json()



def test_continue_points_at_first_incomplete_lesson(migrated_app, migrated_client):
    with migrated_app.app_context():
        seed_all()
    _register(migrated_client)

    hub = migrated_client.get("/levels")
    assert hub.status_code == 200
    assert b"Continue: Noun Gender" in hub.data
    assert b"/lessons/noun-gender" in hub.data

    level = migrated_client.get("/levels/a1")
    assert level.status_code == 200
    assert b"Continue: Noun Gender" in level.data


def test_continue_route_redirects_to_next_lesson(migrated_app, migrated_client):
    with migrated_app.app_context():
        seed_all()
    _register(migrated_client)

    response = migrated_client.get("/continue")
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/lessons/noun-gender")


def test_continue_advances_after_lesson_complete(migrated_app, migrated_client):
    with migrated_app.app_context():
        seed_all()
    user = _register(migrated_client)

    total = len(migrated_client.get("/api/lessons/noun-gender").get_json()["practice"])
    migrated_client.post(
        "/api/lessons/noun-gender/complete",
        json={"exercises_correct": total, "exercises_total": total},
    )

    with migrated_app.app_context():
        db_user = db.session.get(User, user["id"])
        target = continue_target(db_user, level_id="a1")
        assert target is not None
        assert target["kind"] == "lesson"
        assert target["lesson_id"] == "definite-articles"
        assert next_incomplete_lesson(db_user, "a1")["id"] == "definite-articles"

    hub = migrated_client.get("/levels")
    assert b"Continue: Definite Articles" in hub.data

    lesson = migrated_client.get("/lessons/noun-gender")
    assert lesson.status_code == 200
    assert b"Continue: Definite Articles" in lesson.data or b"Definite Articles" in lesson.data
