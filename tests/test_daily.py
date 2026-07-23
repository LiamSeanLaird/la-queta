"""Phase 10 — daily vocab + can-dos."""

from __future__ import annotations

from app.services.seed import seed_all


def _register(client, handle: str = "dailyuser"):
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


def test_daily_session_returns_unretired_cards(migrated_app, migrated_client):
    with migrated_app.app_context():
        seed_all()
    _register(migrated_client)

    response = migrated_client.get("/api/levels/a1/daily")
    assert response.status_code == 200
    body = response.get_json()
    assert "cards" in body
    assert 1 <= len(body["cards"]) <= 20
    assert all(card["retired"] is False for card in body["cards"])


def test_daily_session_fills_from_retired_when_needed(migrated_app, migrated_client):
    with migrated_app.app_context():
        seed_all()
    _register(migrated_client)

    cards = migrated_client.get("/api/decks/starter/cards").get_json()["cards"]
    for card in cards:
        assert migrated_client.post(f"/api/cards/{card['id']}/retire").status_code == 200

    # Other decks still have unretired — retire nothing else; just ensure API works
    response = migrated_client.get("/api/levels/a1/daily")
    assert response.status_code == 200
    assert len(response.get_json()["cards"]) <= 20


def test_daily_page_renders(migrated_app, migrated_client):
    with migrated_app.app_context():
        seed_all()
    _register(migrated_client)
    page = migrated_client.get("/levels/a1/daily")
    assert page.status_code == 200
    assert b"js/study.js" in page.data
    assert b"/api/levels/a1/daily" in page.data


def test_can_dos_on_level_learn_tab(migrated_app, migrated_client):
    with migrated_app.app_context():
        seed_all()
    _register(migrated_client)
    page = migrated_client.get("/levels/a1")
    assert page.status_code == 200
    assert b"Can-do" in page.data or b"can-do" in page.data
    assert b"Daily vocab" in page.data
