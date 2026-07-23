"""Level completeness and continue-path helpers."""

from __future__ import annotations

from sqlalchemy import func, select

from app.extensions import db
from app.models import Card, Deck, Lesson, Level, User, UserCardProgress, UserLessonProgress
from app.services.lessons import list_lessons_for_level

LESSON_WEIGHT = 0.7
VOCAB_WEIGHT = 0.3
RETIRED_SEEN = 3


def level_completeness_pct(user_id: int, level_id: str) -> int:
    total_lessons = db.session.scalar(
        select(func.count()).select_from(Lesson).where(Lesson.level_id == level_id)
    ) or 0
    completed_lessons = db.session.scalar(
        select(func.count())
        .select_from(UserLessonProgress)
        .join(Lesson, Lesson.id == UserLessonProgress.lesson_id)
        .where(
            UserLessonProgress.user_id == user_id,
            UserLessonProgress.completed.is_(True),
            Lesson.level_id == level_id,
        )
    ) or 0

    total_cards = db.session.scalar(
        select(func.count())
        .select_from(Card)
        .join(Deck, Deck.id == Card.deck_id)
        .where(Deck.level_id == level_id)
    ) or 0
    retired_cards = db.session.scalar(
        select(func.count())
        .select_from(UserCardProgress)
        .join(Card, Card.id == UserCardProgress.card_id)
        .join(Deck, Deck.id == Card.deck_id)
        .where(
            UserCardProgress.user_id == user_id,
            UserCardProgress.seen >= RETIRED_SEEN,
            Deck.level_id == level_id,
        )
    ) or 0

    if total_lessons == 0 and total_cards == 0:
        return 0

    lesson_ratio = (completed_lessons / total_lessons) if total_lessons else 0.0
    vocab_ratio = (retired_cards / total_cards) if total_cards else 0.0

    if total_cards == 0:
        return round(100 * lesson_ratio)
    if total_lessons == 0:
        return round(100 * vocab_ratio)
    return round(100 * (LESSON_WEIGHT * lesson_ratio + VOCAB_WEIGHT * vocab_ratio))


def next_incomplete_lesson(user: User, level_id: str) -> dict | None:
    for lesson in list_lessons_for_level(user, level_id):
        if not lesson["completed"]:
            return lesson
    return None


def next_vocab_deck(user: User, level_id: str) -> dict | None:
    from app.services.vocab import list_decks_for_level

    for deck in list_decks_for_level(user, level_id):
        if deck["remaining"] > 0:
            return deck
    return None


def continue_target(user: User, level_id: str | None = None) -> dict | None:
    """
    Next place to send the learner.

    Prefer incomplete lessons, then a vocab deck with remaining cards.
    If level_id is set, stay within that level; else prefer current_level then others.
    """
    levels = db.session.scalars(select(Level).order_by(Level.sort_order, Level.id)).all()
    if not levels:
        return None

    if level_id is not None:
        ordered_ids = [level_id]
    else:
        ordered_ids = []
        if user.current_level_id:
            ordered_ids.append(user.current_level_id)
        for level in levels:
            if level.id not in ordered_ids:
                ordered_ids.append(level.id)

    for lid in ordered_ids:
        lesson = next_incomplete_lesson(user, lid)
        if lesson is not None:
            return {
                "kind": "lesson",
                "level_id": lid,
                "lesson_id": lesson["id"],
                "title": lesson["title"],
                "label": f"Continue: {lesson['title']}",
            }
        deck = next_vocab_deck(user, lid)
        if deck is not None:
            return {
                "kind": "deck",
                "level_id": lid,
                "slug": deck["slug"],
                "title": deck["title"],
                "label": f"Study vocab: {deck['title']}",
            }
    return None
