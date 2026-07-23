"""Vocab decks, session, browse, seen counts."""

from __future__ import annotations

import random

from sqlalchemy import func, select

from app.extensions import db
from app.models import Card, Deck, Level, User, UserCardProgress
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
        "hint": card.hint,
        "tags": card.tags_json or [],
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
        select(Card).where(Card.deck_id == deck.id).order_by(Card.id)
    ).all()
    seen = _seen_map(user.id, [card.id for card in cards])
    return [_card_dict(card, seen.get(card.id, 0)) for card in cards]


def session_for_deck(user: User, slug: str) -> list[dict]:
    cards = list_cards_for_deck(user, slug)
    active = [card for card in cards if not card["retired"]]
    random.shuffle(active)
    return active


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


def deck_card_count(deck_id: int) -> int:
    return db.session.scalar(
        select(func.count()).select_from(Card).where(Card.deck_id == deck_id)
    ) or 0
