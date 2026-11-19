"""Lesson list, detail, and completion."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select

from app.extensions import db
from app.models import Lesson, User, UserLessonProgress
from app.services.errors import ServiceError


def _progress_map(user_id: int, lesson_ids: list[str]) -> dict[str, UserLessonProgress]:
    if not lesson_ids:
        return {}
    rows = db.session.scalars(
        select(UserLessonProgress).where(
            UserLessonProgress.user_id == user_id,
            UserLessonProgress.lesson_id.in_(lesson_ids),
        )
    ).all()
    return {row.lesson_id: row for row in rows}


def lesson_stars(completed: bool, best_first_try: int | None, total: int) -> int:
    """Stars for a lesson: 0 until completed, then 1 to 3 from the best score.

    3 stars: every question right first time. 2 stars: at least 75% right first
    time. 1 star: finished. A completion with no recorded score (before scoring
    existed, or from an older client) is 1 star.
    """
    if not completed:
        return 0
    if best_first_try is None or total <= 0:
        return 1
    if best_first_try >= total:
        return 3
    if best_first_try * 4 >= total * 3:
        return 2
    return 1


def _stars(lesson: Lesson, progress: UserLessonProgress | None) -> int:
    if progress is None:
        return 0
    return lesson_stars(
        progress.completed, progress.best_first_try, len(lesson.practice_json or [])
    )


def list_lessons_for_level(user: User | None, level_id: str) -> list[dict]:
    """Lessons in `level_id` in course order; `user=None` (logged out) has nothing completed."""
    from app.models import Level

    if db.session.get(Level, level_id) is None:
        raise ServiceError("Level not found", 404)

    lessons = db.session.scalars(
        select(Lesson)
        .where(Lesson.level_id == level_id)
        .order_by(Lesson.sort_order, Lesson.id)
    ).all()
    progress = _progress_map(user.id, [lesson.id for lesson in lessons]) if user else {}
    return [
        {
            "id": lesson.id,
            "slug": lesson.slug,
            "title": lesson.title,
            "summary": lesson.summary,
            "sort_order": lesson.sort_order,
            "completed": bool(
                progress.get(lesson.id) and progress[lesson.id].completed
            ),
            "stars": _stars(lesson, progress.get(lesson.id)),
        }
        for lesson in lessons
    ]


def get_lesson(user: User | None, lesson_id: str) -> dict:
    """Lesson content plus `user`'s progress; `user=None` (logged out) has no progress."""
    lesson = db.session.get(Lesson, lesson_id)
    if lesson is None:
        raise ServiceError("Lesson not found", 404)
    progress = None
    if user is not None:
        progress = db.session.scalar(
            select(UserLessonProgress).where(
                UserLessonProgress.user_id == user.id,
                UserLessonProgress.lesson_id == lesson.id,
            )
        )
    return {
        "id": lesson.id,
        "level_id": lesson.level_id,
        "slug": lesson.slug,
        "title": lesson.title,
        "summary": lesson.summary,
        "sort_order": lesson.sort_order,
        "sections": lesson.sections_json or [],
        "practice": lesson.practice_json or [],
        "words": lesson.words_json or [],
        "completed": bool(progress and progress.completed),
        "exercises_correct": progress.exercises_correct if progress else 0,
        "exercises_total": progress.exercises_total if progress else 0,
        "best_first_try": progress.best_first_try if progress else None,
        "stars": _stars(lesson, progress),
    }


def lesson_neighbours(lesson_id: str) -> dict:
    """The lessons just before and after `lesson_id` in course order, ignoring progress.

    Used for the previous / next links on every lesson page, so a visitor can walk
    the course in order. Either side is None at the ends of the level.
    """
    lesson = db.session.get(Lesson, lesson_id)
    if lesson is None:
        raise ServiceError("Lesson not found", 404)
    ordered = list_lessons_for_level(None, lesson.level_id)
    index = next(i for i, row in enumerate(ordered) if row["id"] == lesson.id)
    return {
        "previous": ordered[index - 1] if index > 0 else None,
        "next": ordered[index + 1] if index + 1 < len(ordered) else None,
    }


def complete_lesson(
    user: User,
    lesson_id: str,
    exercises_correct: object,
    exercises_total: object,
    first_try_correct: object = None,
) -> dict:
    """Mark `lesson_id` completed for `user` and keep their best first-try score.

    Completion needs every question answered right (`exercises_correct ==
    exercises_total`). `first_try_correct` is how many were right on the first
    try; it is optional so older clients that do not send it keep working, and
    a retake with a lower score never lowers the stored best.
    """
    lesson = db.session.get(Lesson, lesson_id)
    if lesson is None:
        raise ServiceError("Lesson not found", 404)

    practice = lesson.practice_json or []
    expected_total = len(practice)

    if not isinstance(exercises_correct, int) or not isinstance(exercises_total, int):
        raise ServiceError(
            "exercises_correct and exercises_total must be integers", 400
        )
    if (
        exercises_correct < 0
        or exercises_total < 0
        or exercises_correct > exercises_total
    ):
        raise ServiceError("Invalid exercise score", 400)
    if expected_total == 0:
        raise ServiceError("Lesson has no practice items", 400)
    if exercises_total != expected_total:
        raise ServiceError("Practice score does not match lesson bank", 400)
    if exercises_correct != exercises_total:
        raise ServiceError("All exercises must be correct to complete", 400)
    if first_try_correct is not None and (
        # bool is a subclass of int; true/false is not a score.
        isinstance(first_try_correct, bool)
        or not isinstance(first_try_correct, int)
        or not 0 <= first_try_correct <= exercises_total
    ):
        raise ServiceError(
            "first_try_correct must be an integer from 0 to exercises_total", 400
        )

    progress = db.session.scalar(
        select(UserLessonProgress).where(
            UserLessonProgress.user_id == user.id,
            UserLessonProgress.lesson_id == lesson.id,
        )
    )
    if progress is None:
        progress = UserLessonProgress(user_id=user.id, lesson_id=lesson.id)
        db.session.add(progress)

    first_completion = not progress.completed
    if first_completion:
        # A retake keeps the date the lesson was first completed.
        progress.completed_at = datetime.now(timezone.utc)
    progress.completed = True
    progress.exercises_correct = exercises_correct
    progress.exercises_total = exercises_total
    if first_try_correct is not None and (
        progress.best_first_try is None or first_try_correct > progress.best_first_try
    ):
        progress.best_first_try = first_try_correct
    db.session.commit()

    from app.services.can_dos import goals_unlocked_by_lesson

    lesson_data = get_lesson(user, lesson.id)
    # A retake cannot unlock anything: the goal was already done after the
    # first completion.
    lesson_data["goals_unlocked"] = (
        goals_unlocked_by_lesson(user, lesson.level_id, lesson.id)
        if first_completion
        else []
    )
    return lesson_data
