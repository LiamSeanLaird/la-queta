"""CLI admin metrics for production checks.

Examples:
  poetry run python scripts/admin_metrics.py summary
  poetry run python scripts/admin_metrics.py activity
  poetry run python scripts/admin_metrics.py user --id 12

On the VM:
  source .venv/bin/activate
  set -a && source /etc/la-queta/env && set +a
  python scripts/admin_metrics.py activity
"""

from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone

from sqlalchemy import case, func, select

from app import create_app
from app.extensions import db
from app.models import Card, Deck, Lesson, User, UserCardProgress, UserLessonProgress
from app.services.progress import LESSON_WEIGHT, RETIRED_SEEN, VOCAB_WEIGHT, level_completeness_pct


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


def _complete_pct(lessons_done: int, lessons_total: int, retired: int, cards_total: int) -> int:
    if lessons_total == 0 and cards_total == 0:
        return 0
    lesson_ratio = (lessons_done / lessons_total) if lessons_total else 0.0
    vocab_ratio = (retired / cards_total) if cards_total else 0.0
    if cards_total == 0:
        return round(100 * lesson_ratio)
    if lessons_total == 0:
        return round(100 * vocab_ratio)
    return round(100 * (LESSON_WEIGHT * lesson_ratio + VOCAB_WEIGHT * vocab_ratio))


def cmd_summary(level_id: str) -> None:
    users = db.session.scalar(select(func.count()).select_from(User)) or 0
    since = datetime.now(timezone.utc) - timedelta(hours=24)
    recent = db.session.scalars(
        select(User)
        .where(User.created_at >= since)
        .order_by(User.created_at.desc())
    ).all()

    print(f"users_total: {users}")
    print(f"users_last_24h: {len(recent)}")
    print(f"level_scope: {level_id}")
    if not recent:
        print("new_users: (none)")
        return
    print("new_users:")
    for user in recent:
        created = user.created_at.isoformat() if user.created_at else ""
        print(f"  - id={user.id} handle={user.handle} email={user.email} created_at={created}")


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


def cmd_activity(level_id: str) -> None:
    users = db.session.scalars(select(User).order_by(User.id)).all()
    lessons_total = db.session.scalar(
        select(func.count()).select_from(Lesson).where(Lesson.level_id == level_id)
    ) or 0
    cards_total = db.session.scalar(
        select(func.count())
        .select_from(Card)
        .join(Deck, Deck.id == Card.deck_id)
        .where(Deck.level_id == level_id)
    ) or 0

    lessons_done_rows = db.session.execute(
        select(
            UserLessonProgress.user_id,
            func.count().label("done"),
            func.max(UserLessonProgress.completed_at).label("last_lesson"),
        )
        .join(Lesson, Lesson.id == UserLessonProgress.lesson_id)
        .where(
            UserLessonProgress.completed.is_(True),
            Lesson.level_id == level_id,
        )
        .group_by(UserLessonProgress.user_id)
    ).all()
    lessons_by_user = {row.user_id: int(row.done) for row in lessons_done_rows}
    last_lesson_by_user = {row.user_id: row.last_lesson for row in lessons_done_rows}

    vocab_rows = db.session.execute(
        select(
            UserCardProgress.user_id,
            func.sum(case((UserCardProgress.seen > 0, 1), else_=0)).label("touched"),
            func.sum(case((UserCardProgress.seen >= RETIRED_SEEN, 1), else_=0)).label(
                "retired"
            ),
        )
        .join(Card, Card.id == UserCardProgress.card_id)
        .join(Deck, Deck.id == Card.deck_id)
        .where(Deck.level_id == level_id)
        .group_by(UserCardProgress.user_id)
    ).all()
    touched_by_user = {row.user_id: int(row.touched or 0) for row in vocab_rows}
    retired_by_user = {row.user_id: int(row.retired or 0) for row in vocab_rows}

    rows: list[dict] = []
    for user in users:
        lessons_done = lessons_by_user.get(user.id, 0)
        touched = touched_by_user.get(user.id, 0)
        retired = retired_by_user.get(user.id, 0)
        pct = _complete_pct(lessons_done, lessons_total, retired, cards_total)
        last_lesson = last_lesson_by_user.get(user.id)
        rows.append(
            {
                "id": user.id,
                "handle": user.handle,
                "email": user.email,
                "created_at": user.created_at,
                "current_level_id": user.current_level_id or "",
                "complete_pct": pct,
                "lessons_done": lessons_done,
                "lessons_total": lessons_total,
                "cards_touched": touched,
                "cards_retired": retired,
                "cards_total": cards_total,
                "last_lesson_at": last_lesson,
                "has_activity": lessons_done > 0 or touched > 0,
            }
        )

    rows.sort(key=lambda r: (-r["complete_pct"], -r["id"]))

    active = sum(1 for r in rows if r["has_activity"])
    avg_pct = round(sum(r["complete_pct"] for r in rows) / len(rows)) if rows else 0
    avg_active = (
        round(sum(r["complete_pct"] for r in rows if r["has_activity"]) / active)
        if active
        else 0
    )
    buckets = {
        "0%": 0,
        "1-24%": 0,
        "25-49%": 0,
        "50-74%": 0,
        "75-99%": 0,
        "100%": 0,
    }
    for r in rows:
        pct = r["complete_pct"]
        if pct <= 0:
            buckets["0%"] += 1
        elif pct < 25:
            buckets["1-24%"] += 1
        elif pct < 50:
            buckets["25-49%"] += 1
        elif pct < 75:
            buckets["50-74%"] += 1
        elif pct < 100:
            buckets["75-99%"] += 1
        else:
            buckets["100%"] += 1

    print(f"users_total: {len(rows)}")
    print(f"users_with_activity: {active}")
    print(f"level_scope: {level_id}")
    print(f"avg_complete_pct_all: {avg_pct}")
    print(f"avg_complete_pct_active: {avg_active}")
    print("completion_buckets:")
    for label, count in buckets.items():
        print(f"  {label}: {count}")
    print()
    print(
        f"{'id':>4}  {'pct':>3}  {'lessons':>8}  {'touched':>7}  {'retired':>8}  "
        f"{'created':<20}  {'last_lesson':<20}  handle / email"
    )
    print("-" * 120)
    for r in rows:
        created = r["created_at"].strftime("%Y-%m-%d %H:%M") if r["created_at"] else ""
        last = (
            r["last_lesson_at"].strftime("%Y-%m-%d %H:%M")
            if r["last_lesson_at"]
            else "-"
        )
        print(
            f"{r['id']:>4}  {r['complete_pct']:>3}  "
            f"{r['lessons_done']:>3}/{r['lessons_total']:<4}  "
            f"{r['cards_touched']:>7}  "
            f"{r['cards_retired']:>3}/{r['cards_total']:<4}  "
            f"{created:<20}  {last:<20}  {r['handle']} <{r['email']}>"
        )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="La Queta admin metrics")
    subparsers = parser.add_subparsers(dest="command", required=True)

    summary = subparsers.add_parser("summary", help="Show high-level counts + new users")
    summary.add_argument("--level", default="a1", help="Level scope (default: a1)")

    activity = subparsers.add_parser(
        "activity", help="Show all users activity / completeness table"
    )
    activity.add_argument("--level", default="a1", help="Level scope (default: a1)")

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
        if args.command == "activity":
            cmd_activity(args.level)
            return
        if args.command == "user":
            cmd_user(args.id, args.level)
            return
        raise ValueError(f"Unknown command: {args.command}")


if __name__ == "__main__":
    main()
