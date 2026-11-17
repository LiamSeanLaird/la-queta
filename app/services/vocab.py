"""Vocab decks, session, browse, seen counts."""

from __future__ import annotations

import random
from datetime import UTC, datetime, timedelta

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


def _progress_map(
    user_id: int, card_ids: list[int]
) -> dict[int, tuple[int, datetime | None]]:
    """card_id -> (seen, due_at) for the cards this user has progress on."""
    if not card_ids:
        return {}
    rows = db.session.scalars(
        select(UserCardProgress).where(
            UserCardProgress.user_id == user_id,
            UserCardProgress.card_id.in_(card_ids),
        )
    ).all()
    return {row.card_id: (row.seen, row.due_at) for row in rows}


def _seen_map(user_id: int, card_ids: list[int]) -> dict[int, int]:
    return {
        card_id: seen for card_id, (seen, _) in _progress_map(user_id, card_ids).items()
    }


def _card_dict(card: Card, seen: int, due_at: datetime | None = None) -> dict:
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
        "due_at": due_at.isoformat() if due_at else None,
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
    progress = _progress_map(user.id, [card.id for card in cards])
    return [_card_dict(card, *progress.get(card.id, (0, None))) for card in cards]


def _review_state(card: dict, now: datetime) -> str:
    """Say whether a card is "new", "due" or "early" (studied, not due yet).

    Cards studied before scheduling existed (or through the legacy /seen
    endpoint) have no due date; they count as due so they get a grade.
    """
    if card["due_at"] is None:
        return "new" if card["seen"] == 0 else "due"
    return "due" if datetime.fromisoformat(card["due_at"]) <= now else "early"


def _split_by_state(cards: list[dict], now: datetime) -> dict[str, list[dict]]:
    groups: dict[str, list[dict]] = {"new": [], "due": [], "early": []}
    for card in cards:
        groups[_review_state(card, now)].append(card)
    return groups


def _by_due(cards: list[dict]) -> list[dict]:
    """Oldest due date first; cards with no due date (overdue longest) lead."""
    return sorted(cards, key=lambda card: card["due_at"] or "")


def session_for_deck(user: User, slug: str, now: datetime | None = None) -> list[dict]:
    """Due reviews, then new cards in deck file order, then early reviews.

    Due reviews come first, oldest due date first, so the words the learner
    is about to forget get graded even in a short session. Deck files are
    curated (core verbs first, nouns grouped by topic), so new words keep
    that order. Studied cards that are not due yet come last, shuffled, so a
    learner who keeps going can still review the whole deck.
    """
    now = now or _utc_now()
    cards = list_cards_for_deck(user, slug)
    groups = _split_by_state([card for card in cards if not card["retired"]], now)
    early = groups["early"]
    random.shuffle(early)
    return _by_due(groups["due"]) + groups["new"] + early


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
    progress = _progress_map(user.id, [card.id for card, _ in rows])
    return [
        {**_card_dict(card, *progress.get(card.id, (0, None))), "deck_slug": deck_slug}
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
    user: User, level_id: str, limit: int = DAILY_LIMIT, now: datetime | None = None
) -> list[dict]:
    """Daily review: due cards first, then new words, then the rest.

    1. Unretired cards that are due for review, from any deck in the level,
       oldest due date first. Only studied cards can be due, so these all
       come from decks the learner has reached.
    2. New cards from focus decks (see _focus_deck_slugs), at random.
    3. New cards from the other decks in level order, so the session tops
       up with the vocab that comes next rather than words from lessons far
       ahead.
    4. Unretired cards that are not due yet, soonest due first.
    5. Retired cards from focus decks, as a soft reintroduction.
    The picked cards are shuffled.
    """
    now = now or _utc_now()
    cards = list_cards_for_level(user, level_id)
    focus = _focus_deck_slugs(user, level_id, cards)
    groups = _split_by_state([card for card in cards if not card["retired"]], now)
    focus_new = [card for card in groups["new"] if card["deck_slug"] in focus]
    next_new = [card for card in groups["new"] if card["deck_slug"] not in focus]
    focus_retired = [
        card for card in cards if card["retired"] and card["deck_slug"] in focus
    ]
    random.shuffle(focus_new)
    random.shuffle(focus_retired)
    picked = (
        _by_due(groups["due"])
        + focus_new
        + next_new
        + _by_due(groups["early"])
        + focus_retired
    )[:limit]
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


# Days until the next review after each "Knew it", in order. A card that was
# known once comes back tomorrow, then in 3 days, then a week, and so on.
REVIEW_INTERVALS = (1, 3, 7, 14, 30, 60)

GRADES = ("knew", "not_yet")


def next_interval(current: int, knew: bool) -> int:
    """Interval after a self-grade: next step up on "Knew it", 0 on "Not yet"."""
    if not knew:
        return 0
    for days in REVIEW_INTERVALS:
        if days > current:
            return days
    return REVIEW_INTERVALS[-1]


def _utc_now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def grade_card(
    user: User, card_id: int, grade: str, now: datetime | None = None
) -> dict:
    """Record a self-grade after the learner flipped a card.

    "knew" moves the card up REVIEW_INTERVALS and counts as one more `seen`,
    so a card retires after the learner knew it RETIRED_SEEN times.
    "not_yet" drops the interval to 0 and makes the card due again now;
    `seen` stays the same, so not remembering a word never retires it.
    """
    if grade not in GRADES:
        raise ServiceError("grade must be 'knew' or 'not_yet'", 400)
    card = db.session.get(Card, card_id)
    if card is None:
        raise ServiceError("Card not found", 404)

    now = now or _utc_now()
    knew = grade == "knew"
    progress = db.session.scalar(
        select(UserCardProgress).where(
            UserCardProgress.user_id == user.id,
            UserCardProgress.card_id == card.id,
        )
    )
    if progress is None:
        progress = UserCardProgress(
            user_id=user.id, card_id=card.id, seen=0, interval_days=0
        )
        db.session.add(progress)

    progress.interval_days = next_interval(progress.interval_days or 0, knew)
    progress.due_at = now + timedelta(days=progress.interval_days)
    progress.last_reviewed_at = now
    if knew:
        progress.seen += 1
    db.session.commit()
    return {
        **_card_dict(card, progress.seen),
        "interval_days": progress.interval_days,
        "due_at": progress.due_at.isoformat(),
    }


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
    """Start the deck over: every card is new again for this user.

    last_reviewed_at is kept as history.
    """
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
            row.interval_days = 0
            row.due_at = None
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
