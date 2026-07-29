"""CLI admin metrics for production checks.

Examples:
  poetry run python scripts/admin_metrics.py summary
  poetry run python scripts/admin_metrics.py user --id 12
"""

from __future__ import annotations

import argparse

from sqlalchemy import func, select

from app import create_app
from app.extensions import db
from app.models import Card, Deck, Lesson, User, UserCardProgress, UserLessonProgress
from app.services.progress import RETIRED_SEEN, level_completeness_pct


def _lesson_counts(user_id: int, level_id: str) -> tuple[int, int]:
    total = db.session.scalar(
        select(func.count()).select_from(Lesson).where(Lesson.level_id == level_id)
    ) or 0
    done = db.session.scalar(
        select(func.count())
        .select_from(UserLessonProgress)
        .join(Lesson, Lesson.id == UserLessonProgress.lesson_id)
        .where(
            UserLessonProgress.user_id == user_id,
            UserLessonProgress.completed.is_(True),
            Lesson.level_id == level_id,
        )
    ) or 0
    return done, total


def _vocab_counts(user_id: int, level_id: str) -> tuple[int, int]:
    total = db.session.scalar(
        select(func.count())
        .select_from(Card)
        .join(Deck, Deck.id == Card.deck_id)
        .where(Deck.level_id == level_id)
    ) or 0
    retired = db.session.scalar(
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
    return retired, total


def cmd_summary(level_id: str) -> None:
    users = db.session.scalar(select(func.count()).select_from(User)) or 0
    print(f"users_total: {users}")
    print(f"level_scope: {level_id}")


def cmd_user(user_id: int, level_id: str) -> None:
    user = db.session.get(User, user_id)
    if user is None:
        print(f"User not found: {user_id}")
        return

    lessons_done, lessons_total = _lesson_counts(user.id, level_id)
    retired_cards, total_cards = _vocab_counts(user.id, level_id)
    complete_pct = level_completeness_pct(user.id, level_id)

    print(f"user_id: {user.id}")
    print(f"handle: {user.handle}")
    print(f"email: {user.email}")
    print(f"created_at: {user.created_at.isoformat() if user.created_at else ''}")
    print(f"current_level_id: {user.current_level_id or ''}")
    print(f"level_scope: {level_id}")
    print(f"complete_pct: {complete_pct}")
    print(f"lessons_done: {lessons_done}/{lessons_total}")
    print(f"cards_retired: {retired_cards}/{total_cards} (retired threshold: {RETIRED_SEEN})")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="La Queta admin metrics")
    subparsers = parser.add_subparsers(dest="command", required=True)

    summary = subparsers.add_parser("summary", help="Show high-level counts")
    summary.add_argument("--level", default="a1", help="Level scope (default: a1)")

    user = subparsers.add_parser("user", help="Show one user completeness details")
    user.add_argument("--id", type=int, required=True, help="User id")
    user.add_argument("--level", default="a1", help="Level scope (default: a1)")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    app = create_app()
    with app.app_context():
        if args.command == "summary":
            cmd_summary(args.level)
            return
        if args.command == "user":
            cmd_user(args.id, args.level)
            return
        raise ValueError(f"Unknown command: {args.command}")


if __name__ == "__main__":
    main()
