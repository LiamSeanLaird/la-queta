"""Level completeness (derived, not stored)."""

from __future__ import annotations

from sqlalchemy import func, select

from app.extensions import db
from app.models import Card, Deck, Lesson, UserCardProgress, UserLessonProgress

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
