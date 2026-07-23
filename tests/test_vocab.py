"""Phase 5 — vocab decks, session, seen, browse."""

from __future__ import annotations

from app.services.seed import seed_all


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



def test_seed_decks_into_a1(migrated_app):
    with migrated_app.app_context():
        seed_all()
        from sqlalchemy import func, select

        from app.extensions import db
        from app.models import Card, Deck

        assert db.session.scalar(select(func.count()).select_from(Deck)) == 8
        assert db.session.scalar(select(func.count()).select_from(Card)) == 244
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
    assert len(decks) == 8
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


def test_card_payload_includes_prototype_meta(migrated_app, migrated_client):
    with migrated_app.app_context():
        seed_all()
    _register(migrated_client)

    starter = migrated_client.get("/api/decks/starter/cards").get_json()["cards"]
    bon_dia = next(c for c in starter if c["external_id"] == "greet_001")
    assert bon_dia["pronunciation"] == "bohn DEE-ah"
    assert bon_dia["pos"] == "phrase"
    assert bon_dia["tags"] == ["greetings"]
    assert bon_dia["forms"] == []

    days = migrated_client.get("/api/decks/days_months/cards").get_json()["cards"]
    dilluns = next(c for c in days if c["external_id"] == "dm_001")
    assert dilluns["gender"] == "m"
    assert dilluns["plural"] == "dilluns"
    assert dilluns["pos"] == "noun"

    browse = migrated_client.get("/decks/days_months/browse")
    assert browse.status_code == 200
    assert b"masculine" in browse.data
    assert b"dee-YOONS" in browse.data


def test_retire_marks_card_and_excludes_from_session(migrated_app, migrated_client):
    with migrated_app.app_context():
        seed_all()
    _register(migrated_client)

    cards = migrated_client.get("/api/decks/starter/cards").get_json()["cards"]
    first = cards[0]
    assert first["retired"] is False

    retired = migrated_client.post(f"/api/cards/{first['id']}/retire")
    assert retired.status_code == 200
    body = retired.get_json()
    assert body["retired"] is True
    assert body["seen"] >= 3

    session = migrated_client.get("/api/decks/starter/session").get_json()["cards"]
    assert all(card["id"] != first["id"] for card in session)

    browse = migrated_client.get("/decks/starter/browse")
    assert browse.status_code == 200
    assert b"Retired" in browse.data
    assert b"data-retire" in browse.data


def test_unretire_deck_resets_seen_and_restores_session(migrated_app, migrated_client):
    with migrated_app.app_context():
        seed_all()
    _register(migrated_client)

    cards = migrated_client.get("/api/decks/starter/cards").get_json()["cards"]
    for card in cards:
        assert migrated_client.post(f"/api/cards/{card['id']}/retire").status_code == 200

    session = migrated_client.get("/api/decks/starter/session").get_json()["cards"]
    assert session == []

    deck_page = migrated_client.get("/decks/starter")
    assert deck_page.status_code == 200
    assert b"Unretire deck" in deck_page.data
    assert b"data-unretire" in deck_page.data

    unretire = migrated_client.post("/api/decks/starter/unretire")
    assert unretire.status_code == 200
    body = unretire.get_json()
    assert body["retired"] == 0
    assert body["remaining"] == body["total"] == len(cards)

    restored = migrated_client.get("/api/decks/starter/cards").get_json()["cards"]
    assert all(card["seen"] == 0 and card["retired"] is False for card in restored)
    session = migrated_client.get("/api/decks/starter/session").get_json()["cards"]
    assert len(session) == len(cards)
