"""Phase 11 — listening / speaking practice items."""

from __future__ import annotations

from app.services.seed import seed_all


def _register(client, handle: str = "listener"):
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


def test_lessons_include_listen_and_speak_practice(migrated_app, migrated_client):
    with migrated_app.app_context():
        seed_all()
    _register(migrated_client)

    body = migrated_client.get("/api/lessons/noun-gender").get_json()
    kinds = {item["kind"] for item in body["practice"]}
    assert "listen_choice" in kinds
    assert "listen_type" in kinds
    assert "speak" in kinds
    listen = next(item for item in body["practice"] if item["kind"] == "listen_choice")
    assert listen.get("speak")


def test_practice_page_loads_speech_js(migrated_app, migrated_client):
    with migrated_app.app_context():
        seed_all()
    _register(migrated_client)
    page = migrated_client.get("/lessons/noun-gender?tab=practice")
    assert page.status_code == 200
    assert b"js/speech.js" in page.data
    assert b"js/practice.js" in page.data
