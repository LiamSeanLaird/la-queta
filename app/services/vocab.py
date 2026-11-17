"""Vocab decks, session, browse, seen counts."""

from __future__ import annotations

import random

from sqlalchemy import func, select

from app.extensions import db
from app.models import (
    Card,
    Deck,
    Lesson,
    Level,
    User,
    UserCardProgress,
    UserLessonProgress,
)
from app.services.errors import ServiceError
from app.services.progress import RETIRED_SEEN


def _get_deck(slug: str) -> Deck:
    deck = db.session.scalar(select(Deck).where(Deck.slug == slug))
    if deck is None:
        raise ServiceError("Deck not found", 404)
    return deck


def _seen_map(user_id: int, card_ids: list[int]) -> dict[int, int]:
    if not card_ids:
        return {}
    rows = db.session.scalars(
        select(UserCardProgress).where(
            UserCardProgress.user_id == user_id,
            UserCardProgress.card_id.in_(card_ids),
        )
    ).all()
    return {row.card_id: row.seen for row in rows}


def _card_dict(card: Card, seen: int) -> dict:
    return {
        "id": card.id,
        "external_id": card.external_id,
        "catalan": card.catalan,
        "english": card.english,
        "pronunciation": card.pronunciation or "",
        "hint": card.hint or "",
        "pos": card.pos or "",
        "gender": card.gender,
        "plural": card.plural,
        "tags": card.tags_json or [],
        "forms": card.forms_json or [],
        "seen": seen,
        "retired": seen >= RETIRED_SEEN,
    }


def list_decks_for_level(user: User, level_id: str) -> list[dict]:
    if db.session.get(Level, level_id) is None:
        raise ServiceError("Level not found", 404)

    decks = db.session.scalars(
        select(Deck).where(Deck.level_id == level_id).order_by(Deck.sort_order, Deck.slug)
    ).all()
    result = []
    for deck in decks:
        cards = db.session.scalars(select(Card).where(Card.deck_id == deck.id)).all()
        seen = _seen_map(user.id, [card.id for card in cards])
        total = len(cards)
        retired = sum(1 for card in cards if seen.get(card.id, 0) >= RETIRED_SEEN)
        result.append(
            {
                "slug": deck.slug,
                "title": deck.title,
                "sort_order": deck.sort_order,
                "total": total,
                "retired": retired,
                "remaining": total - retired,
            }
        )
    return result


def list_cards_for_deck(user: User, slug: str) -> list[dict]:
    deck = _get_deck(slug)
    cards = db.session.scalars(
        select(Card)
        .where(Card.deck_id == deck.id)
        .order_by(Card.position, Card.id)
    ).all()
    seen = _seen_map(user.id, [card.id for card in cards])
    return [_card_dict(card, seen.get(card.id, 0)) for card in cards]


def session_for_deck(user: User, slug: str) -> list[dict]:
    """Shuffled review of cards already seen, then new cards in deck file order.

    Deck files are curated (core verbs first, nouns grouped by topic), so a
    learner meets new words in that order. Cards they have already seen are
    reviewed first, shuffled, so recall does not lean on position.
    """
    cards = list_cards_for_deck(user, slug)
    active = [card for card in cards if not card["retired"]]
    review = [card for card in active if card["seen"] > 0]
    new = [card for card in active if card["seen"] == 0]
    random.shuffle(review)
    return review + new


DAILY_LIMIT = 20


def list_cards_for_level(user: User, level_id: str) -> list[dict]:
    if db.session.get(Level, level_id) is None:
        raise ServiceError("Level not found", 404)

    rows = db.session.execute(
        select(Card, Deck.slug)
        .join(Deck, Deck.id == Card.deck_id)
        .where(Deck.level_id == level_id)
        .order_by(Deck.sort_order, Deck.slug, Card.position, Card.id)
    ).all()
    seen = _seen_map(user.id, [card.id for card, _ in rows])
    return [
        {**_card_dict(card, seen.get(card.id, 0)), "deck_slug": deck_slug}
        for card, deck_slug in rows
    ]


def _focus_deck_slugs(user: User, level_id: str, cards: list[dict]) -> set[str]:
    """Decks the learner has reached: started in study, or linked to a done lesson.

    A learner who has reached none yet gets the level's first deck, which
    matches the first lesson.
    """
    started = {card["deck_slug"] for card in cards if card["seen"] > 0}
    completed_lesson_decks = db.session.scalars(
        select(Lesson.deck_slug)
        .join(UserLessonProgress, UserLessonProgress.lesson_id == Lesson.id)
        .where(
            UserLessonProgress.user_id == user.id,
            UserLessonProgress.completed.is_(True),
            Lesson.level_id == level_id,
            Lesson.deck_slug.is_not(None),
        )
    ).all()
    focus = started | set(completed_lesson_decks)
    if not focus and cards:
        focus = {cards[0]["deck_slug"]}
    return focus


def daily_session_for_level(
    user: User, level_id: str, limit: int = DAILY_LIMIT
) -> list[dict]:
    """Daily review drawn from the decks the learner has reached.

    1. Unretired cards from focus decks (see _focus_deck_slugs), at random.
    2. If that is not enough, unretired cards from the other decks in level
       order, so the session tops up with the vocab that comes next rather
       than words from lessons far ahead.
    3. Then retired cards from focus decks, as a soft reintroduction.
    The picked cards are shuffled.
    """
    cards = list_cards_for_level(user, level_id)
    focus = _focus_deck_slugs(user, level_id, cards)
    in_focus = [card for card in cards if card["deck_slug"] in focus]
    focus_active = [card for card in in_focus if not card["retired"]]
    focus_retired = [card for card in in_focus if card["retired"]]
    next_active = [
        card
        for card in cards
        if card["deck_slug"] not in focus and not card["retired"]
    ]
    random.shuffle(focus_active)
    random.shuffle(focus_retired)
    picked = (focus_active + next_active + focus_retired)[:limit]
    random.shuffle(picked)
    return picked


def increment_seen(user: User, card_id: int) -> dict:
    card = db.session.get(Card, card_id)
    if card is None:
        raise ServiceError("Card not found", 404)

    progress = db.session.scalar(
        select(UserCardProgress).where(
            UserCardProgress.user_id == user.id,
            UserCardProgress.card_id == card.id,
        )
    )
    if progress is None:
        progress = UserCardProgress(user_id=user.id, card_id=card.id, seen=0)
        db.session.add(progress)

    progress.seen += 1
    db.session.commit()
    return _card_dict(card, progress.seen)


def retire_card(user: User, card_id: int) -> dict:
    """Mark card retired for this user (seen = max(seen, RETIRED_SEEN))."""
    card = db.session.get(Card, card_id)
    if card is None:
        raise ServiceError("Card not found", 404)

    progress = db.session.scalar(
        select(UserCardProgress).where(
            UserCardProgress.user_id == user.id,
            UserCardProgress.card_id == card.id,
        )
    )
    if progress is None:
        progress = UserCardProgress(
            user_id=user.id, card_id=card.id, seen=RETIRED_SEEN
        )
        db.session.add(progress)
    else:
        progress.seen = max(progress.seen, RETIRED_SEEN)

    db.session.commit()
    return _card_dict(card, progress.seen)


def unretire_deck(user: User, slug: str) -> dict:
    """Reset seen to 0 for every card in the deck for this user."""
    deck = _get_deck(slug)
    cards = db.session.scalars(select(Card).where(Card.deck_id == deck.id)).all()
    card_ids = [card.id for card in cards]
    if card_ids:
        rows = db.session.scalars(
            select(UserCardProgress).where(
                UserCardProgress.user_id == user.id,
                UserCardProgress.card_id.in_(card_ids),
            )
        ).all()
        for row in rows:
            row.seen = 0
        db.session.commit()

    total = len(cards)
    return {
        "slug": deck.slug,
        "title": deck.title,
        "total": total,
        "retired": 0,
        "remaining": total,
    }


def deck_card_count(deck_id: int) -> int:
    return db.session.scalar(
        select(func.count()).select_from(Card).where(Card.deck_id == deck_id)
    ) or 0
