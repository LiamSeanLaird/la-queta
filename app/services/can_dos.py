"""A1 goals (can-dos) loaded from content/a1_can_dos.json."""

from __future__ import annotations

import json
from pathlib import Path

from app.models import User
from app.services.lessons import list_lessons_for_level

ROOT = Path(__file__).resolve().parents[2]
CAN_DOS_PATH = ROOT / "content" / "a1_can_dos.json"


def _raw_can_dos() -> list[dict]:
    if not CAN_DOS_PATH.is_file():
        return []
    return json.loads(CAN_DOS_PATH.read_text(encoding="utf-8"))


def list_can_dos_for_level(user: User, level_id: str) -> list[dict]:
    if level_id != "a1":
        return []
    return _can_dos_items(_raw_can_dos(), list_lessons_for_level(user, level_id))


def _can_dos_items(raw: list[dict], lessons: list[dict]) -> list[dict]:
    by_id = {row["id"]: row for row in lessons}
    completed = {row["id"] for row in lessons if row["completed"]}

    result = []
    for item in raw:
        lesson_ids = list(item.get("lesson_ids") or [])
        known = [lid for lid in lesson_ids if lid in by_id]
        lessons_done = sum(1 for lid in known if lid in completed)
        lessons_total = len(known)
        done = lessons_total > 0 and lessons_done == lessons_total
        result.append(
            {
                "id": item["id"],
                "label": item["label"],
                "lesson_ids": lesson_ids,
                "lessons_done": lessons_done,
                "lessons_total": lessons_total,
                "done": done,
            }
        )
    return result


def next_goal(items: list[dict], next_lesson_id: str | None) -> dict | None:
    """
    The unfinished goal the learner is working towards.

    That is the goal holding the next lesson Continue would open, so the card
    and the Continue button agree. If that lesson belongs to no goal (or all
    lessons are done), fall back to the first unfinished goal with lessons.
    """
    open_goals = [item for item in items if not item["done"] and item["lessons_total"]]
    if next_lesson_id is not None:
        for item in open_goals:
            if next_lesson_id in item["lesson_ids"]:
                return item
    return open_goals[0] if open_goals else None


def can_dos_progress(user: User, level_id: str) -> dict:
    if level_id == "a1":
        lessons = list_lessons_for_level(user, level_id)
        items = _can_dos_items(_raw_can_dos(), lessons)
        next_lesson_id = next(
            (row["id"] for row in lessons if not row["completed"]), None
        )
    else:
        items, next_lesson_id = [], None
    done = sum(1 for item in items if item["done"])
    total = len(items)
    return {
        "items": items,
        "done": done,
        "total": total,
        "pct": round(100 * done / total) if total else 0,
        "next": next_goal(items, next_lesson_id),
    }


def learn_groups_for_level(user: User | None, level_id: str) -> list[dict]:
    """Ordered Learn-tab sections: each goal + its lessons."""
    lessons = list_lessons_for_level(user, level_id)
    by_id = {row["id"]: row for row in lessons}
    completed = {row["id"] for row in lessons if row["completed"]}
    seen: set[str] = set()
    groups: list[dict] = []

    for item in _raw_can_dos() if level_id == "a1" else []:
        lesson_ids = list(item.get("lesson_ids") or [])
        group_lessons = [by_id[lid] for lid in lesson_ids if lid in by_id]
        for row in group_lessons:
            seen.add(row["id"])
        lessons_done = sum(1 for row in group_lessons if row["id"] in completed)
        lessons_total = len(group_lessons)
        groups.append(
            {
                "id": item["id"],
                "label": item["label"],
                "done": lessons_total > 0 and lessons_done == lessons_total,
                "lessons_done": lessons_done,
                "lessons_total": lessons_total,
                "lessons": group_lessons,
            }
        )

    leftover = [row for row in lessons if row["id"] not in seen]
    if leftover:
        lessons_done = sum(1 for row in leftover if row["id"] in completed)
        groups.append(
            {
                "id": "more",
                "label": "More",
                "done": lessons_done == len(leftover),
                "lessons_done": lessons_done,
                "lessons_total": len(leftover),
                "lessons": leftover,
            }
        )
    return groups


def vocab_groups_for_level(user: User, level_id: str) -> list[dict]:
    """Ordered Vocab-tab sections: each goal + its decks (skip goals with no decks)."""
    from app.services.vocab import list_decks_for_level

    decks = list_decks_for_level(user, level_id)
    by_slug = {row["slug"]: row for row in decks}
    seen: set[str] = set()
    groups: list[dict] = []

    def with_done(row: dict) -> dict:
        total = int(row.get("total") or 0)
        remaining = int(row.get("remaining") or 0)
        done = total > 0 and remaining == 0
        return {**row, "done": done}

    for item in _raw_can_dos() if level_id == "a1" else []:
        slugs = list(item.get("deck_slugs") or [])
        # Inside a goal, decks follow the lesson order (Deck.sort_order), so the
        # deck for the earliest lesson comes first.
        group_decks = sorted(
            (with_done(by_slug[slug]) for slug in slugs if slug in by_slug),
            key=lambda row: row["sort_order"],
        )
        if not group_decks:
            continue
        for row in group_decks:
            seen.add(row["slug"])
        decks_done = sum(1 for row in group_decks if row["done"])
        decks_total = len(group_decks)
        groups.append(
            {
                "id": item["id"],
                "label": item["label"],
                "done": decks_total > 0 and decks_done == decks_total,
                "decks_done": decks_done,
                "decks_total": decks_total,
                "decks": group_decks,
            }
        )

    leftover = [with_done(row) for row in decks if row["slug"] not in seen]
    if leftover:
        decks_done = sum(1 for row in leftover if row["done"])
        groups.append(
            {
                "id": "more",
                "label": "More",
                "done": decks_done == len(leftover),
                "decks_done": decks_done,
                "decks_total": len(leftover),
                "decks": leftover,
            }
        )
    return groups


def goals_unlocked_by_lesson(user: User, level_id: str, lesson_id: str) -> list[dict]:
    """Goals that become done only because `lesson_id` is now complete."""
    lessons = list_lessons_for_level(user, level_id)
    known = {row["id"] for row in lessons}
    completed = {row["id"] for row in lessons if row["completed"]}
    if lesson_id not in completed:
        return []

    before = completed - {lesson_id}
    unlocked = []
    for item in _raw_can_dos() if level_id == "a1" else []:
        ids = [lid for lid in (item.get("lesson_ids") or []) if lid in known]
        if not ids or lesson_id not in ids:
            continue
        now_done = all(lid in completed for lid in ids)
        was_done = all(lid in before for lid in ids)
        if now_done and not was_done:
            unlocked.append({"id": item["id"], "label": item["label"]})
    return unlocked
