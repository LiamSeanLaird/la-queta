"""Content checks for the first two lessons, where most learners start."""

from __future__ import annotations

import json
from pathlib import Path

LESSONS = Path(__file__).resolve().parent.parent / "content" / "lessons"


def _lesson(name: str) -> dict:
    return json.loads((LESSONS / name).read_text(encoding="utf-8"))


def _text(lesson: dict) -> str:
    parts = []
    for section in lesson["sections"]:
        parts.append(section.get("content", ""))
        for item in section.get("items", []):
            parts.append(item["catalan"])
    return "\n".join(parts)


def test_noun_gender_teaches_un_and_una_before_using_them():
    lesson = _lesson("01-noun-gender.json")
    first_un = next(
        i
        for i, section in enumerate(lesson["sections"])
        if any(item["catalan"].startswith("un ") for item in section.get("items", []))
    )
    teaching = lesson["sections"][first_un - 1]
    assert teaching["type"] == "text"
    assert "un " in teaching["content"] and "una " in teaching["content"]
    assert any(item.get("answer") == "una" for item in lesson["practice"])


def test_definite_articles_plural_rule_is_correct():
    lesson = _lesson("02-definite-articles.json")
    text = _text(lesson)
    assert "wait" not in text
    assert "la taula → les taules" in text
    assert "-a change it to -es" in text
    assert "la universitat" in text
    answers = {a for item in lesson["practice"] for a in item.get("answers", [])}
    assert "les taules" in answers


def test_practice_ids_are_unique_across_lessons():
    ids = [
        item["id"]
        for path in sorted(LESSONS.glob("*.json"))
        for item in json.loads(path.read_text(encoding="utf-8"))["practice"]
    ]
    assert len(ids) == len(set(ids))


def test_ser_vs_estar_uses_ser_for_where_places_are():
    lesson = _lesson("03-ser-vs-estar.json")
    notes = {
        item["catalan"]: item.get("note", "")
        for section in lesson["sections"]
        for item in section.get("items", [])
    }
    assert notes["On ets?"].endswith("- ser")
    assert notes["On és l'estació?"].endswith("- ser")
    station = next(item for item in lesson["practice"] if item["id"] == "se-p03")
    assert station["answer"] == "On és l'estació? (ser)"
    for item in lesson["practice"]:
        if item["kind"] == "multiple_choice":
            assert item["answer"] in item["options"]
