"""Phase 4 — lessons seed, API, completion."""

from __future__ import annotations

from app.services.seed import seed_all, seed_lessons, seed_levels


def _register(client, handle: str = "liam"):
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



def test_seed_lessons_into_a1(migrated_app):
    with migrated_app.app_context():
        seed_all()
        assert seed_lessons() == 6


def test_list_lessons_requires_auth(migrated_client):
    response = migrated_client.get("/api/levels/a1/lessons")
    assert response.status_code == 401


def test_list_a1_lessons_and_empty_a2(migrated_app, migrated_client):
    with migrated_app.app_context():
        seed_all()
    _register(migrated_client)

    a1 = migrated_client.get("/api/levels/a1/lessons")
    assert a1.status_code == 200
    lessons = a1.get_json()["lessons"]
    assert len(lessons) == 6
    assert lessons[0]["id"] == "noun-gender"
    assert lessons[0]["completed"] is False

    a2 = migrated_client.get("/api/levels/a2/lessons")
    assert a2.status_code == 200
    assert a2.get_json()["lessons"] == []


def test_lesson_detail_includes_sections(migrated_app, migrated_client):
    with migrated_app.app_context():
        seed_all()
    _register(migrated_client)
    response = migrated_client.get("/api/lessons/noun-gender")
    assert response.status_code == 200
    body = response.get_json()
    assert body["title"] == "Noun Gender"
    assert body["level_id"] == "a1"
    assert all(section["type"] != "exercise" for section in body["sections"])
    assert len(body["practice"]) >= 8


def test_complete_lesson_persists_progress(migrated_app, migrated_client):
    with migrated_app.app_context():
        seed_all()
    _register(migrated_client)

    total = len(migrated_client.get("/api/lessons/noun-gender").get_json()["practice"])
    response = migrated_client.post(
        "/api/lessons/noun-gender/complete",
        json={"exercises_correct": total, "exercises_total": total},
    )
    assert response.status_code == 200
    assert response.get_json()["completed"] is True
    assert response.get_json()["exercises_correct"] == total

    listed = migrated_client.get("/api/levels/a1/lessons").get_json()["lessons"]
    by_id = {row["id"]: row for row in listed}
    assert by_id["noun-gender"]["completed"] is True

    levels = migrated_client.get("/api/levels").get_json()["levels"]
    a1 = next(row for row in levels if row["id"] == "a1")
    # 1/6 lessons done, 0/189 vocab retired → round(100 * (0.7/6 + 0)) == 12
    assert a1["complete_pct"] == 12


def test_complete_lesson_rejects_bad_score(migrated_app, migrated_client):
    with migrated_app.app_context():
        seed_levels()
        seed_lessons()
    _register(migrated_client)
    total = len(migrated_client.get("/api/lessons/noun-gender").get_json()["practice"])
    response = migrated_client.post(
        "/api/lessons/noun-gender/complete",
        json={"exercises_correct": total + 1, "exercises_total": total},
    )
    assert response.status_code == 400


def test_complete_lesson_rejects_imperfect_score(migrated_app, migrated_client):
    with migrated_app.app_context():
        seed_all()
    _register(migrated_client)
    total = len(migrated_client.get("/api/lessons/noun-gender").get_json()["practice"])
    response = migrated_client.post(
        "/api/lessons/noun-gender/complete",
        json={"exercises_correct": max(total - 1, 0), "exercises_total": total},
    )
    assert response.status_code == 400
    assert b"correct" in response.data
