import json
import os
import glob

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
LESSONS_DIR = os.path.join(os.path.dirname(__file__), "lessons")


# ── Vocab decks ───────────────────────────────────────────

def list_decks():
    paths = sorted(glob.glob(os.path.join(DATA_DIR, "*_deck*.json")))
    decks = []
    for path in paths:
        slug = os.path.basename(path).split("_deck")[0]
        cards = _load_deck_file(path)
        decks.append({
            "slug": slug,
            "name": slug.replace("_", " ").title(),
            "total": len(cards),
        })
    return decks


def _load_deck_file(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _deck_path(slug):
    for suffix in (f"{slug}_deck_INXS.json", f"{slug}_deck.json"):
        path = os.path.join(DATA_DIR, suffix)
        if os.path.exists(path):
            return path
    return os.path.join(DATA_DIR, f"{slug}_deck.json")


def load_cards(slug):
    path = _deck_path(slug)
    if not os.path.exists(path):
        return None
    return _load_deck_file(path)


# ── Lessons ───────────────────────────────────────────────

def list_lessons():
    paths = sorted(glob.glob(os.path.join(LESSONS_DIR, "*.json")))
    lessons = []
    for path in paths:
        with open(path, "r", encoding="utf-8") as f:
            lesson = json.load(f)
        exercise_count = sum(1 for s in lesson["sections"] if s["type"] == "exercise")
        lessons.append({
            "id": lesson["id"],
            "title": lesson["title"],
            "order": lesson["order"],
            "summary": lesson["summary"],
            "exercise_count": exercise_count,
        })
    return lessons


def load_lesson(lesson_id: str):
    for path in glob.glob(os.path.join(LESSONS_DIR, "*.json")):
        with open(path, "r", encoding="utf-8") as f:
            lesson = json.load(f)
        if lesson["id"] == lesson_id:
            return lesson
    return None
