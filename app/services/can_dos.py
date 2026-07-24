"""A1 can-do checklist loaded from content/a1_can_dos.json."""

from __future__ import annotations

import json
from pathlib import Path

from app.services.lessons import list_lessons_for_level
from app.models import User

ROOT = Path(__file__).resolve().parents[2]
CAN_DOS_PATH = ROOT / "content" / "a1_can_dos.json"


def list_can_dos_for_level(user: User, level_id: str) -> list[dict]:
    if level_id != "a1":
        return []
    if not CAN_DOS_PATH.is_file():
        return []

    raw = json.loads(CAN_DOS_PATH.read_text(encoding="utf-8"))
    lessons = list_lessons_for_level(user, level_id)
    completed = {row["id"] for row in lessons if row["completed"]}

    result = []
    for item in raw:
        lesson_ids = list(item.get("lesson_ids") or [])
        done = bool(lesson_ids) and all(lid in completed for lid in lesson_ids)
        result.append(
            {
                "id": item["id"],
                "label": item["label"],
                "lesson_ids": lesson_ids,
                "done": done,
            }
        )
    return result


def can_dos_progress(user: User, level_id: str) -> dict:
    items = list_can_dos_for_level(user, level_id)
    done = sum(1 for item in items if item["done"])
    return {
        "items": items,
        "done": done,
        "total": len(items),
    }
