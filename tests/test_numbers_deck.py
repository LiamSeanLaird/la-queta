"""The Numbers lesson has its own vocab deck, and card pos values come from one set."""

from __future__ import annotations

import json
from pathlib import Path

from sqlalchemy import select

from app.extensions import db
from app.models import Deck
from app.services.seed import seed_all

CONTENT = Path(__file__).resolve().parents[1] / "content"

# Every card's `pos` must be one of these. Add to this set deliberately.
ALLOWED_POS = {"noun", "verb", "adjective", "adverb", "number", "phrase", "interjection"}


def _deck(slug: str) -> list[dict]:
    return json.loads((CONTENT / "decks" / f"{slug}_deck.json").read_text(encoding="utf-8"))


def test_every_card_pos_comes_from_the_fixed_set():
    for path in sorted((CONTENT / "decks").glob("*_deck*.json")):
        for card in json.loads(path.read_text(encoding="utf-8")):
            assert card.get("pos") in ALLOWED_POS, (path.name, card["id"], card.get("pos"))


def test_numbers_deck_covers_zero_to_twenty_tens_hundred_and_thousand():
    cards = _deck("numbers")
    assert 20 <= len(cards) <= 30
    assert {card["pos"] for card in cards} == {"number"}
    assert {tuple(card["tags"]) for card in cards} == {("numbers",)}
    words = [card["catalan"] for card in cards]
    assert words[:4] == ["zero", "un / una", "dos / dues", "tres"]
    for word in ["quinze", "setze", "disset", "vint", "trenta", "noranta", "cent", "mil"]:
        assert word in words
    assert all(card["id"].startswith("nm_") for card in cards)


def test_numbers_lesson_links_to_numbers_deck_and_it_sorts_in_place(migrated_app):
    lesson = json.loads((CONTENT / "lessons" / "07-numbers.json").read_text(encoding="utf-8"))
    assert lesson["deck"] == "numbers"
    with migrated_app.app_context():
        seed_all()
        slugs = db.session.scalars(select(Deck.slug).order_by(Deck.sort_order)).all()
        assert slugs.index("starter") + 1 == slugs.index("numbers")
        assert slugs.index("numbers") + 1 == slugs.index("days_months")
        deck = db.session.scalar(select(Deck).where(Deck.slug == "numbers"))
        assert deck.title == "Numbers"


def test_numbers_deck_is_in_the_identity_goal():
    goals = json.loads((CONTENT / "a1_can_dos.json").read_text(encoding="utf-8"))
    goal = next(g for g in goals if "numbers" in g["lesson_ids"])
    assert "numbers" in goal["deck_slugs"]
