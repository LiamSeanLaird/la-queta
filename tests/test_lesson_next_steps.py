"""After a lesson: offer its matching vocab deck and the next lesson."""

from __future__ import annotations

import json
from pathlib import Path

from app.extensions import db
from app.models import Card, Deck, User, UserCardProgress
from app.services.progress import RETIRED_SEEN, lesson_next_steps
from app.services.seed import seed_all

CONTENT = Path(__file__).resolve().parents[1] / "content"


def _register(client, handle: str = "stepper"):
    response = client.post(
        "/api/auth/register",
        json={"handle": handle, "email": f"{handle}@example.com", "password": "password1"},
    )
    assert response.status_code == 201
    return response.get_json()


def _complete(client, lesson_id: str) -> None:
    total = len(client.get(f"/api/lessons/{lesson_id}").get_json()["practice"])
    response = client.post(
        f"/api/lessons/{lesson_id}/complete",
        json={"exercises_correct": total, "exercises_total": total},
    )
    assert response.status_code == 200


def test_every_lesson_deck_exists():
    deck_slugs = {path.name.split("_deck")[0] for path in (CONTENT / "decks").glob("*_deck*.json")}
    for path in sorted((CONTENT / "lessons").glob("*.json")):
        raw = json.loads(path.read_text(encoding="utf-8"))
        if "deck" in raw:
            assert raw["deck"] in deck_slugs, f"{path.name}: unknown deck {raw['deck']!r}"


def test_practice_done_panel_offers_deck_then_next_lesson(migrated_app, migrated_client):
    with migrated_app.app_context():
        seed_all()
    _register(migrated_client)

    page = migrated_client.get("/lessons/noun-gender?tab=practice").get_data(as_text=True)
    assert 'id="practice-done"' in page
    assert "/decks/everyday/study" in page
    assert "Study vocab: Describing Words" in page
    assert "Next lesson: Definite Articles" in page
    assert page.index("Study vocab: Describing Words") < page.index("Next lesson: Definite Articles")

    # Same choices once the lesson is done, and the Learn tab offers the deck too.
    _complete(migrated_client, "noun-gender")
    page = migrated_client.get("/lessons/noun-gender?tab=practice").get_data(as_text=True)
    assert "Next lesson: Definite Articles" in page
    learn = migrated_client.get("/lessons/noun-gender").get_data(as_text=True)
    assert "Study vocab: Describing Words" in learn
    assert "Next lesson: Definite Articles" in learn


def test_lesson_without_deck_makes_next_lesson_primary(migrated_app, migrated_client):
    with migrated_app.app_context():
        seed_all()
    _register(migrated_client)

    page = migrated_client.get("/lessons/numbers?tab=practice").get_data(as_text=True)
    assert "Study vocab:" not in page
    assert 'btn--primary btn--block" href="/lessons/time-calendar"' in page


def test_next_steps_skip_finished_deck_and_wrap_to_skipped_lessons(migrated_app, migrated_client):
    with migrated_app.app_context():
        seed_all()
    user = _register(migrated_client)
    _complete(migrated_client, "noun-gender")

    with migrated_app.app_context():
        db_user = db.session.get(User, user["id"])
        steps = lesson_next_steps(db_user, "public-admin")
        assert steps["deck"]["slug"] == "admin"
        # Last lesson wraps to the first one not yet done.
        assert steps["next_lesson"]["id"] == "definite-articles"

        deck = db.session.scalar(db.select(Deck).where(Deck.slug == "admin"))
        for card in db.session.scalars(db.select(Card).where(Card.deck_id == deck.id)):
            db.session.add(UserCardProgress(user_id=db_user.id, card_id=card.id, seen=RETIRED_SEEN))
        db.session.commit()
        assert lesson_next_steps(db_user, "public-admin")["deck"] is None
