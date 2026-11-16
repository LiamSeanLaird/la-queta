"""Vocab decks follow the lesson order."""

from __future__ import annotations

import json
from pathlib import Path

from sqlalchemy import select

from app.extensions import db
from app.models import Deck, Lesson, User
from app.services.progress import continue_target
from app.services.seed import deck_order_from_lessons, seed_all

CONTENT = Path(__file__).resolve().parents[1] / "content"


def _register(client, handle: str = "orderly"):
    response = client.post(
        "/api/auth/register",
        json={"handle": handle, "email": f"{handle}@example.com", "password": "password1"},
    )
    assert response.status_code == 201


def test_every_deck_is_linked_from_a_lesson():
    deck_slugs = {p.name.split("_deck")[0] for p in (CONTENT / "decks").glob("*_deck*.json")}
    assert set(deck_order_from_lessons()) == deck_slugs


def test_seeded_deck_order_follows_first_linked_lesson(migrated_app):
    with migrated_app.app_context():
        seed_all()
        lessons = db.session.scalars(select(Lesson).order_by(Lesson.sort_order)).all()
        expected: list[str] = []
        for lesson in lessons:
            if lesson.deck_slug and lesson.deck_slug not in expected:
                expected.append(lesson.deck_slug)
        decks = db.session.scalars(select(Deck).order_by(Deck.sort_order)).all()
        assert [deck.slug for deck in decks] == expected
        assert expected[:5] == ["everyday", "food_drink", "core_verbs", "social_phrases", "starter"]
        assert len({deck.sort_order for deck in decks}) == len(decks)


def test_unlinked_deck_sorts_after_linked_decks(migrated_app, monkeypatch):
    import app.services.seed as seed

    order = deck_order_from_lessons()
    order.pop("signs")
    monkeypatch.setattr(seed, "deck_order_from_lessons", lambda: dict(order))
    with migrated_app.app_context():
        seed_all()
        decks = db.session.scalars(select(Deck).order_by(Deck.sort_order)).all()
        assert decks[-1].slug == "signs"
        assert decks[-1].sort_order > len(order)


def test_vocab_tab_lists_goal_decks_in_lesson_order(migrated_app, migrated_client):
    with migrated_app.app_context():
        seed_all()
    _register(migrated_client)

    page = migrated_client.get("/levels/a1?tab=vocab").get_data(as_text=True)
    # Core grammar: noun-gender (lesson 1) links Describing Words, present-tense links Core Verbs.
    assert page.index("Describing Words") < page.index("Core Verbs")
    # Introduce myself: question-words (5), introductions (6), time-calendar (8).
    assert (
        page.index("Questions &amp; Useful Phrases")
        < page.index("Greetings &amp; Introductions")
        < page.index("Days, Months &amp; Time")
    )


def test_continue_after_all_lessons_offers_first_lesson_deck(migrated_app, migrated_client):
    with migrated_app.app_context():
        seed_all()
    _register(migrated_client)

    for path in sorted((CONTENT / "lessons").glob("*.json")):
        raw = json.loads(path.read_text(encoding="utf-8"))
        total = len(raw["practice"])
        response = migrated_client.post(
            f"/api/lessons/{raw['id']}/complete",
            json={"exercises_correct": total, "exercises_total": total},
        )
        assert response.status_code == 200

    with migrated_app.app_context():
        user = db.session.scalar(select(User).where(User.handle == "orderly"))
        target = continue_target(user, "a1")
    assert target["kind"] == "deck"
    assert target["slug"] == "everyday"
    assert target["label"] == "Study vocab: Describing Words"
