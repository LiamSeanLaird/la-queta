"""The 'Next goal' line on the /levels card."""

from __future__ import annotations

from app.extensions import db
from app.models import User, UserLessonProgress
from app.services.can_dos import next_goal
from app.services.lessons import list_lessons_for_level
from app.services.seed import seed_all

CORE_GRAMMAR = [
    "noun-gender",
    "definite-articles",
    "ser-vs-estar",
    "present-tense",
    "question-words",
]


def _item(goal_id: str, lesson_ids: list[str], done: int) -> dict:
    return {
        "id": goal_id,
        "label": goal_id,
        "lesson_ids": lesson_ids,
        "lessons_done": done,
        "lessons_total": len(lesson_ids),
        "done": done == len(lesson_ids),
    }


def test_next_goal_is_the_one_holding_the_next_lesson():
    items = [
        _item("first", ["a", "b"], 1),
        _item("second", ["c", "d"], 0),
    ]
    assert next_goal(items, "c")["id"] == "second"
    assert next_goal(items, "b")["id"] == "first"


def test_next_goal_falls_back_to_first_unfinished():
    items = [
        _item("done", ["a"], 1),
        _item("empty", [], 0),
        _item("open", ["b", "c"], 1),
    ]
    # Lesson in no goal, or no lesson left: first unfinished goal that has lessons.
    assert next_goal(items, "zzz")["id"] == "open"
    assert next_goal(items, None)["id"] == "open"
    # A finished goal is never "next", even if it lists the lesson.
    assert next_goal(items, "a")["id"] == "open"


def test_next_goal_none_when_all_done():
    assert next_goal([_item("done", ["a"], 1)], None) is None
    assert next_goal([], "a") is None


def _register(client, handle: str = "goaler") -> dict:
    response = client.post(
        "/api/auth/register",
        json={
            "handle": handle,
            "email": f"{handle}@example.com",
            "password": "password1",
        },
    )
    assert response.status_code == 201
    return response.get_json()


def _complete(user_id: int, lesson_ids: list[str]) -> None:
    for lesson_id in lesson_ids:
        db.session.add(
            UserLessonProgress(
                user_id=user_id,
                lesson_id=lesson_id,
                completed=True,
                exercises_correct=1,
                exercises_total=1,
            )
        )
    db.session.commit()


def _goals_line(page: str) -> str:
    chunk = page.split('class="level-tile__goals"')[1].split("</p>")[0]
    return " ".join(chunk.replace(">", "> ").split())


def test_levels_card_shows_next_goal_progress(migrated_app, migrated_client):
    with migrated_app.app_context():
        seed_all()
    body = _register(migrated_client)

    line = _goals_line(migrated_client.get("/levels").get_data(as_text=True))
    assert "Next goal:" in line
    assert "Build core grammar</span> - 0 of 5 lessons" in line
    assert "See all 7 goals</button>" in line
    assert "0/7" not in line

    with migrated_app.app_context():
        _complete(body["id"], CORE_GRAMMAR[:2])
    line = _goals_line(migrated_client.get("/levels").get_data(as_text=True))
    assert "Build core grammar</span> - 2 of 5 lessons" in line
    assert "See all 7 goals</button>" in line

    with migrated_app.app_context():
        _complete(body["id"], CORE_GRAMMAR[2:])
    line = _goals_line(migrated_client.get("/levels").get_data(as_text=True))
    assert "Introduce myself &amp; use numbers and time</span> - 0 of 3 lessons" in line
    assert "1/7 goals done</button>" in line
    # The goals dialog is still reachable from the card.
    assert "data-can-dos-open" in line


def test_levels_card_when_every_goal_is_done(migrated_app, migrated_client):
    with migrated_app.app_context():
        seed_all()
    body = _register(migrated_client, "finisher")
    with migrated_app.app_context():
        user = db.session.get(User, body["id"])
        _complete(body["id"], [row["id"] for row in list_lessons_for_level(user, "a1")])

    line = _goals_line(migrated_client.get("/levels").get_data(as_text=True))
    assert "Next goal" not in line
    assert "All 7 goals complete</button>" in line
    assert "level-tile__done-check" in line
