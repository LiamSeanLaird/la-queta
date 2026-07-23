"""Phase 5 — vocab decks, session, seen, browse."""

from __future__ import annotations

from app.services.seed import seed_all


def _register(client, handle: str = "liam"):
    response = client.post("/api/auth/register", json={"handle": handle})
    assert response.status_code == 201
    return response.get_json()


def test_seed_decks_into_a1(migrated_app):
    with migrated_app.app_context():
        seed_all()
        from sqlalchemy import func, select

        from app.extensions import db
        from app.models import Card, Deck

        assert db.session.scalar(select(func.count()).select_from(Deck)) == 7
        assert db.session.scalar(select(func.count()).select_from(Card)) == 189
        a2_decks = db.session.scalar(
            select(func.count()).select_from(Deck).where(Deck.level_id == "a2")
        )
        assert a2_decks == 0


def test_list_decks_requires_auth(migrated_client):
    assert migrated_client.get("/api/levels/a1/decks").status_code == 401


def test_list_a1_decks_and_empty_a2(migrated_app, migrated_client):
    with migrated_app.app_context():
        seed_all()
    _register(migrated_client)

    a1 = migrated_client.get("/api/levels/a1/decks")
    assert a1.status_code == 200
    decks = a1.get_json()["decks"]
    assert len(decks) == 7
    assert decks[0]["slug"] == "starter"
    assert decks[0]["total"] > 0
    assert decks[0]["retired"] == 0
    assert decks[0]["remaining"] == decks[0]["total"]

    a2 = migrated_client.get("/api/levels/a2/decks")
    assert a2.status_code == 200
    assert a2.get_json()["decks"] == []


def test_session_excludes_retired_cards(migrated_app, migrated_client):
    with migrated_app.app_context():
        seed_all()
    _register(migrated_client)

    cards = migrated_client.get("/api/decks/starter/cards").get_json()["cards"]
    first = cards[0]
    for _ in range(3):
        seen = migrated_client.post(f"/api/cards/{first['id']}/seen")
        assert seen.status_code == 200
    assert seen.get_json()["seen"] == 3
    assert seen.get_json()["retired"] is True

    session = migrated_client.get("/api/decks/starter/session").get_json()["cards"]
    assert all(card["id"] != first["id"] for card in session)
    assert len(session) == len(cards) - 1


def test_browse_includes_seen(migrated_app, migrated_client):
    with migrated_app.app_context():
        seed_all()
    _register(migrated_client)
    cards = migrated_client.get("/api/decks/starter/cards").get_json()["cards"]
    assert cards[0]["seen"] == 0
    migrated_client.post(f"/api/cards/{cards[0]['id']}/seen")
    cards = migrated_client.get("/api/decks/starter/cards").get_json()["cards"]
    assert cards[0]["seen"] == 1
