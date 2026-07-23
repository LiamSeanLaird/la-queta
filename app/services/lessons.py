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


def list_lessons_for_level(user: User, level_id: str) -> list[dict]:
    from app.models import Level

    if db.session.get(Level, level_id) is None:
        raise ServiceError("Level not found", 404)

    lessons = db.session.scalars(
        select(Lesson)
        .where(Lesson.level_id == level_id)
        .order_by(Lesson.sort_order, Lesson.id)
    ).all()
    progress = _progress_map(user.id, [lesson.id for lesson in lessons])
    return [
        {
            "id": lesson.id,
            "slug": lesson.slug,
            "title": lesson.title,
            "summary": lesson.summary,
            "sort_order": lesson.sort_order,
            "completed": bool(progress.get(lesson.id) and progress[lesson.id].completed),
        }
        for lesson in lessons
    ]


def get_lesson(user: User, lesson_id: str) -> dict:
    lesson = db.session.get(Lesson, lesson_id)
    if lesson is None:
        raise ServiceError("Lesson not found", 404)
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
        "completed": bool(progress and progress.completed),
        "exercises_correct": progress.exercises_correct if progress else 0,
        "exercises_total": progress.exercises_total if progress else 0,
    }


def complete_lesson(
    user: User,
    lesson_id: str,
    exercises_correct: object,
    exercises_total: object,
) -> dict:
    lesson = db.session.get(Lesson, lesson_id)
    if lesson is None:
        raise ServiceError("Lesson not found", 404)

    practice = lesson.practice_json or []
    expected_total = len(practice)

    if not isinstance(exercises_correct, int) or not isinstance(exercises_total, int):
        raise ServiceError("exercises_correct and exercises_total must be integers", 400)
    if exercises_correct < 0 or exercises_total < 0 or exercises_correct > exercises_total:
        raise ServiceError("Invalid exercise score", 400)
    if expected_total == 0:
        raise ServiceError("Lesson has no practice items", 400)
    if exercises_total != expected_total:
        raise ServiceError("Practice score does not match lesson bank", 400)
    if exercises_correct != exercises_total:
        raise ServiceError("All exercises must be correct to complete", 400)

    progress = db.session.scalar(
        select(UserLessonProgress).where(
            UserLessonProgress.user_id == user.id,
            UserLessonProgress.lesson_id == lesson.id,
        )
    )
    if progress is None:
        progress = UserLessonProgress(user_id=user.id, lesson_id=lesson.id)
        db.session.add(progress)

    progress.completed = True
    progress.exercises_correct = exercises_correct
    progress.exercises_total = exercises_total
    progress.completed_at = datetime.now(timezone.utc)
    db.session.commit()
    return get_lesson(user, lesson.id)
