"""Level completeness and continue-path helpers."""

from __future__ import annotations

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
from app.services.lessons import list_lessons_for_level

LESSON_WEIGHT = 0.7
VOCAB_WEIGHT = 0.3
RETIRED_SEEN = 3


def level_progress_counts(user_id: int, level_id: str) -> dict:
    """Counts a learner recognises: lessons done and words learned in a level.

    A word is "learned" once its card is retired (seen >= RETIRED_SEEN) and
    "started" once it has been seen at least once.
    """
    total_lessons = (
        db.session.scalar(
            select(func.count()).select_from(Lesson).where(Lesson.level_id == level_id)
        )
        or 0
    )
    completed_lessons = (
        db.session.scalar(
            select(func.count())
            .select_from(UserLessonProgress)
            .join(Lesson, Lesson.id == UserLessonProgress.lesson_id)
            .where(
                UserLessonProgress.user_id == user_id,
                UserLessonProgress.completed.is_(True),
                Lesson.level_id == level_id,
            )
        )
        or 0
    )

    total_cards = (
        db.session.scalar(
            select(func.count())
            .select_from(Card)
            .join(Deck, Deck.id == Card.deck_id)
            .where(Deck.level_id == level_id)
        )
        or 0
    )
    card_progress = (
        select(func.count())
        .select_from(UserCardProgress)
        .join(Card, Card.id == UserCardProgress.card_id)
        .join(Deck, Deck.id == Card.deck_id)
        .where(UserCardProgress.user_id == user_id, Deck.level_id == level_id)
    )
    retired_cards = (
        db.session.scalar(card_progress.where(UserCardProgress.seen >= RETIRED_SEEN))
        or 0
    )
    started_cards = (
        db.session.scalar(card_progress.where(UserCardProgress.seen > 0)) or 0
    )

    return {
        "lessons_done": completed_lessons,
        "lessons_total": total_lessons,
        "words_learned": retired_cards,
        "words_started": started_cards,
        "words_total": total_cards,
    }


def completeness_pct(counts: dict) -> int:
    total_lessons = counts["lessons_total"]
    total_cards = counts["words_total"]
    if total_lessons == 0 and total_cards == 0:
        return 0

    lesson_ratio = (counts["lessons_done"] / total_lessons) if total_lessons else 0.0
    vocab_ratio = (counts["words_learned"] / total_cards) if total_cards else 0.0

    if total_cards == 0:
        return round(100 * lesson_ratio)
    if total_lessons == 0:
        return round(100 * vocab_ratio)
    return round(100 * (LESSON_WEIGHT * lesson_ratio + VOCAB_WEIGHT * vocab_ratio))


def progress_summary(counts: dict) -> str:
    """Short line such as "3 of 20 lessons · 89 words learned".

    Words show as "learned" once any card is retired. Before that, cards the
    learner has studied show as "started", so early vocab work is visible too.
    Nothing is said about words the learner has not touched yet.
    """
    parts = []
    if counts["lessons_total"]:
        parts.append(f"{counts['lessons_done']} of {counts['lessons_total']} lessons")
    learned = counts["words_learned"]
    started = counts["words_started"]
    if learned:
        parts.append(f"{learned} {'word' if learned == 1 else 'words'} learned")
    elif started:
        parts.append(f"{started} {'word' if started == 1 else 'words'} started")
    return " · ".join(parts)


def level_completeness_pct(user_id: int, level_id: str) -> int:
    return completeness_pct(level_progress_counts(user_id, level_id))


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
    levels = db.session.scalars(
        select(Level).order_by(Level.sort_order, Level.id)
    ).all()
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


def lesson_next_steps(user: User, lesson_id: str) -> dict:
    """
    Where to go after finishing a lesson's practice.

    `deck` is the lesson's matching vocab deck while it still has cards to learn.
    `next_lesson` is the first incomplete lesson after this one (wrapping round),
    never this lesson itself, so the answer is the same before and after this
    lesson is marked complete.
    """
    from app.services.vocab import list_decks_for_level

    lesson = db.session.get(Lesson, lesson_id)
    if lesson is None:
        return {"deck": None, "next_lesson": None}

    deck = None
    if lesson.deck_slug:
        stats = next(
            (
                row
                for row in list_decks_for_level(user, lesson.level_id)
                if row["slug"] == lesson.deck_slug
            ),
            None,
        )
        if stats is not None and stats["remaining"] > 0:
            deck = stats

    lessons = list_lessons_for_level(user, lesson.level_id)
    index = next((i for i, row in enumerate(lessons) if row["id"] == lesson.id), 0)
    # Look forward from this lesson first, then wrap round to any skipped earlier ones.
    ordered = lessons[index + 1 :] + lessons[:index]
    next_lesson = next((row for row in ordered if not row["completed"]), None)
    return {"deck": deck, "next_lesson": next_lesson}


def _deck_lesson_ids(slug: str, level_id: str) -> set[str]:
    return set(
        db.session.scalars(
            select(Lesson.id).where(
                Lesson.level_id == level_id, Lesson.deck_slug == slug
            )
        )
    )


def deck_lessons(user: User, slug: str, level_id: str) -> list[dict]:
    """Lessons in `level_id` that link to the deck `slug`, in lesson order, with progress."""
    linked_ids = _deck_lesson_ids(slug, level_id)
    return [
        row for row in list_lessons_for_level(user, level_id) if row["id"] in linked_ids
    ]


def deck_next_lesson(user: User, slug: str, level_id: str) -> dict | None:
    """
    Lesson to offer after a study session on the deck `slug`.

    If a lesson that links to this deck is not done yet, offer it, so a learner
    who opened the vocab first still meets its grammar. Otherwise offer the
    first incomplete lesson after the deck's lesson (wrapping round), which is
    the same lesson the lesson's own done panel offers as 'Next lesson'.
    Decks with no linked lesson fall back to the level's next incomplete lesson.
    """
    lessons = list_lessons_for_level(user, level_id)
    linked_ids = _deck_lesson_ids(slug, level_id)
    linked = [i for i, row in enumerate(lessons) if row["id"] in linked_ids]
    if not linked:
        return next((row for row in lessons if not row["completed"]), None)
    for i in linked:
        if not lessons[i]["completed"]:
            return lessons[i]
    last = linked[-1]
    ordered = lessons[last + 1 :] + lessons[:last]
    return next((row for row in ordered if not row["completed"]), None)
