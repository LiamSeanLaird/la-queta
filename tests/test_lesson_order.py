"""Lessons have one order: the Learn tab's goal order, which "Next lesson" and Continue follow."""

from __future__ import annotations

import json
from pathlib import Path

from sqlalchemy import select

from app.extensions import db
from app.models import User
from app.services.progress import continue_target
from app.services.seed import seed_all

CONTENT = Path(__file__).resolve().parents[1] / "content"


def _lessons_by_order() -> list[tuple[str, dict]]:
    rows = [
        (path.name, json.loads(path.read_text(encoding="utf-8")))
        for path in (CONTENT / "lessons").glob("*.json")
    ]
    return sorted(rows, key=lambda row: row[1]["order"])


def _goal_lesson_ids() -> list[str]:
    goals = json.loads((CONTENT / "a1_can_dos.json").read_text(encoding="utf-8"))
    return [lesson_id for goal in goals for lesson_id in goal["lesson_ids"]]


def test_lesson_order_matches_learn_tab_goal_order():
    # The Learn tab lists lessons goal by goal; `order` must give the same sequence.
    assert [raw["id"] for _, raw in _lessons_by_order()] == _goal_lesson_ids()


def test_lesson_file_names_carry_their_order():
    lessons = _lessons_by_order()
    assert [raw["order"] for _, raw in lessons] == list(range(1, len(lessons) + 1))
    for name, raw in lessons:
        assert name == f"{raw['order']:02d}-{raw['id']}.json"


def _register(client):
    response = client.post(
        "/api/auth/register",
        json={"handle": "inorder", "email": "inorder@example.com", "password": "password1"},
    )
    assert response.status_code == 201


def _complete(client, lesson_id: str) -> None:
    total = len(client.get(f"/api/lessons/{lesson_id}").get_json()["practice"])
    response = client.post(
        f"/api/lessons/{lesson_id}/complete",
        json={"exercises_correct": total, "exercises_total": total},
    )
    assert response.status_code == 200


def test_next_lesson_is_the_next_row_on_the_learn_tab(migrated_app, migrated_client):
    with migrated_app.app_context():
        seed_all()
    _register(migrated_client)

    learn = migrated_client.get("/levels/a1").get_data(as_text=True)
    # The Learn tab shows introductions, then numbers, then time-calendar.
    assert (
        learn.index('href="/lessons/introductions"')
        < learn.index('href="/lessons/numbers"')
        < learn.index('href="/lessons/time-calendar"')
    )

    # A learner who works down the Learn tab is sent to the next row, not elsewhere.
    for lesson_id in _goal_lesson_ids()[:6]:
        _complete(migrated_client, lesson_id)
    practice = migrated_client.get("/lessons/introductions?tab=practice").get_data(as_text=True)
    assert 'href="/lessons/numbers"' in practice
    assert "/lessons/food-cafe" not in practice

    with migrated_app.app_context():
        user = db.session.scalar(select(User).where(User.handle == "inorder"))
        target = continue_target(user, "a1")
    assert target["kind"] == "lesson"
    assert target["lesson_id"] == "numbers"
