"""The "You've finished A1" moment on the last lesson and on the hub."""

from __future__ import annotations

from app.services.seed import seed_all


def _register(client, handle: str = "finisher"):
    response = client.post(
        "/api/auth/register",
        json={
            "handle": handle,
            "email": f"{handle}@example.com",
            "password": "password1",
        },
    )
    assert response.status_code == 201


def _lesson_ids(client) -> list[str]:
    rows = client.get("/api/levels/a1/lessons").get_json()
    rows = rows["lessons"] if isinstance(rows, dict) else rows
    return [row["id"] for row in rows]


def _complete(client, lesson_id: str) -> None:
    total = len(client.get(f"/api/lessons/{lesson_id}").get_json()["practice"])
    response = client.post(
        f"/api/lessons/{lesson_id}/complete",
        json={"exercises_correct": total, "exercises_total": total},
    )
    assert response.status_code == 200


def _setup(migrated_app, migrated_client) -> list[str]:
    with migrated_app.app_context():
        seed_all()
    _register(migrated_client)
    return _lesson_ids(migrated_client)


def test_last_remaining_lesson_shows_finished_moment(migrated_app, migrated_client):
    ids = _setup(migrated_app, migrated_client)
    # Leave a middle lesson for last, so "last" means last remaining, not last in order.
    last = ids[3]
    for lesson_id in ids:
        if lesson_id != last:
            _complete(migrated_client, lesson_id)

    page = migrated_client.get(f"/lessons/{last}?tab=practice").get_data(as_text=True)
    assert "You've finished A1 - well done." in page
    assert "A2 is not here yet" in page
    assert 'href="/levels/a1/daily"' in page
    assert "Lesson complete - well done." not in page

    # The hub does not show it until that lesson is done too.
    hub = migrated_client.get("/levels").get_data(as_text=True)
    assert 'id="finished-a1"' not in hub

    _complete(migrated_client, last)
    hub = migrated_client.get("/levels").get_data(as_text=True)
    assert 'id="finished-a1"' in hub
    assert "You've finished A1" in hub
    assert "A2 is not here yet." in hub


def test_other_lessons_keep_the_normal_completion_step(migrated_app, migrated_client):
    ids = _setup(migrated_app, migrated_client)
    for lesson_id in ids[:-2]:
        _complete(migrated_client, lesson_id)

    page = migrated_client.get(f"/lessons/{ids[-1]}?tab=practice").get_data(
        as_text=True
    )
    assert "Lesson complete - well done." in page
    assert "finished A1" not in page
    assert 'id="finished-a1"' not in migrated_client.get("/levels").get_data(
        as_text=True
    )


def test_logged_out_never_sees_finished_moment(migrated_app, migrated_client):
    with migrated_app.app_context():
        seed_all()
    ids = _lesson_ids_public(migrated_client)
    page = migrated_client.get(f"/lessons/{ids[-1]}?tab=practice").get_data(
        as_text=True
    )
    assert "finished A1" not in page
    assert "Create a free account to save this lesson" in page


def _lesson_ids_public(client) -> list[str]:
    import re

    html = client.get("/").get_data(as_text=True)
    seen: list[str] = []
    for lesson_id in re.findall(r'href="/lessons/([a-z0-9-]+)"', html):
        if lesson_id not in seen:
            seen.append(lesson_id)
    return seen


def test_carried_over_last_lesson_shows_finished_moment(migrated_app, migrated_client):
    ids = _setup(migrated_app, migrated_client)
    for lesson_id in ids:
        _complete(migrated_client, lesson_id)

    page = migrated_client.get(f"/lessons/{ids[-1]}?saved=1&finished=1").get_data(
        as_text=True
    )
    assert 'id="finished-level"' in page
    # Without ?saved=1 a completed lesson's Learn tab stays as it was.
    page = migrated_client.get(f"/lessons/{ids[-1]}").get_data(as_text=True)
    assert 'id="finished-level"' not in page


def test_redoing_a_lesson_after_finishing_keeps_normal_step(
    migrated_app, migrated_client
):
    ids = _setup(migrated_app, migrated_client)
    for lesson_id in ids:
        _complete(migrated_client, lesson_id)

    page = migrated_client.get(f"/lessons/{ids[3]}?tab=practice").get_data(
        as_text=True
    )
    assert "Lesson complete - well done." in page
    assert "finished A1" not in page


def test_carried_over_lesson_that_was_already_done_keeps_learn_tab(
    migrated_app, migrated_client
):
    ids = _setup(migrated_app, migrated_client)
    for lesson_id in ids:
        _complete(migrated_client, lesson_id)

    # A returning learner redoes lesson 3 logged out, then signs in: gate.js reads
    # the lesson first, sees it was already complete, and lands without the marker.
    assert migrated_client.get(f"/api/lessons/{ids[3]}").get_json()["completed"]
    _complete(migrated_client, ids[3])
    page = migrated_client.get(f"/lessons/{ids[3]}?saved=1").get_data(as_text=True)
    assert "Saved to your account." in page
    assert 'id="finished-level"' not in page
