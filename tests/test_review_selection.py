"""Spaced repetition slice 3: due cards come first in deck study and daily vocab."""

from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy import select

from app.extensions import db
from app.models import Card, Deck, User, UserCardProgress
from app.services.progress import RETIRED_SEEN
from app.services.seed import seed_all
from app.services.vocab import (
    daily_session_for_level,
    grade_card,
    session_for_deck,
    unretire_deck,
)

NOW = datetime(2026, 11, 17, 9, 30)


def _user() -> User:
    user = User(handle="sr", email="sr@example.com", password_hash="x")
    db.session.add(user)
    db.session.commit()
    return user


def _decks() -> list[Deck]:
    return db.session.scalars(
        select(Deck).where(Deck.level_id == "a1").order_by(Deck.sort_order, Deck.slug)
    ).all()


def _cards(deck: Deck) -> list[Card]:
    return db.session.scalars(
        select(Card).where(Card.deck_id == deck.id).order_by(Card.position, Card.id)
    ).all()


def _progress(user: User, card: Card, seen: int, due_at: datetime | None) -> None:
    db.session.add(
        UserCardProgress(
            user_id=user.id,
            card_id=card.id,
            seen=seen,
            interval_days=1 if due_at else 0,
            due_at=due_at,
        )
    )
    db.session.commit()


def test_deck_session_orders_due_then_new_then_early(migrated_app):
    with migrated_app.app_context():
        seed_all()
        user = _user()
        deck = _decks()[0]
        cards = _cards(deck)
        legacy, overdue, due_today, early, retired = cards[:5]
        _progress(user, legacy, 2, None)  # studied via the old /seen, never graded
        _progress(user, overdue, 1, NOW - timedelta(days=2))
        _progress(user, due_today, 1, NOW - timedelta(hours=1))
        _progress(user, early, 1, NOW + timedelta(days=1))
        _progress(user, retired, RETIRED_SEEN, NOW - timedelta(days=5))

        ids = [card["id"] for card in session_for_deck(user, deck.slug, now=NOW)]

        assert ids[:3] == [legacy.id, overdue.id, due_today.id]
        new_ids = [card.id for card in cards[5:]]
        assert ids[3 : 3 + len(new_ids)] == new_ids  # deck file order kept
        assert ids[-1] == early.id
        assert retired.id not in ids


def test_not_yet_card_is_due_not_new(migrated_app):
    with migrated_app.app_context():
        seed_all()
        user = _user()
        deck = _decks()[0]
        cards = _cards(deck)
        grade_card(user, cards[-1].id, "not_yet", now=NOW)

        ids = [card["id"] for card in session_for_deck(user, deck.slug, now=NOW)]
        assert ids[0] == cards[-1].id


def test_daily_puts_due_cards_in_and_leaves_early_reviews_out(migrated_app):
    with migrated_app.app_context():
        seed_all()
        user = _user()
        first, second = _decks()[:2]
        first_cards = _cards(first)
        second_cards = _cards(second)
        # Two due words in the second deck, and early reviews in the first.
        due = second_cards[:2]
        for card in due:
            _progress(user, card, 1, NOW - timedelta(days=1))
        early = first_cards[:3]
        for card in early:
            _progress(user, card, 1, NOW + timedelta(days=3))

        for _ in range(5):  # the pick is random; the rules must hold every time
            ids = {card["id"] for card in daily_session_for_level(user, "a1", now=NOW)}
            assert {card.id for card in due} <= ids
            assert not {card.id for card in early} & ids

        # With room for only two cards, both are the due ones.
        small = daily_session_for_level(user, "a1", limit=2, now=NOW)
        assert {card["id"] for card in small} == {card.id for card in due}


def test_daily_is_due_cards_on_a_later_day(migrated_app):
    with migrated_app.app_context():
        seed_all()
        user = _user()
        first = _decks()[0]
        cards = _cards(first)
        for card in cards[:4]:
            grade_card(user, card.id, "knew", now=NOW)

        same_day = {
            card["id"] for card in daily_session_for_level(user, "a1", limit=4, now=NOW)
        }
        assert not same_day & {card.id for card in cards[:4]}

        next_day = daily_session_for_level(
            user, "a1", limit=4, now=NOW + timedelta(days=1)
        )
        assert {card["id"] for card in next_day} == {card.id for card in cards[:4]}


def test_unretire_deck_makes_cards_new_again(migrated_app):
    with migrated_app.app_context():
        seed_all()
        user = _user()
        deck = _decks()[0]
        card = _cards(deck)[0]
        _progress(user, card, RETIRED_SEEN, NOW + timedelta(days=7))

        unretire_deck(user, deck.slug)

        row = db.session.scalar(
            select(UserCardProgress).where(UserCardProgress.card_id == card.id)
        )
        assert (row.seen, row.interval_days, row.due_at) == (0, 0, None)
        ids = [c["id"] for c in session_for_deck(user, deck.slug, now=NOW)]
        assert ids[0] == card.id  # first again in deck file order, as a new card
