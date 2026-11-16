"""Idempotent content seed."""

from __future__ import annotations

import json
from pathlib import Path

from sqlalchemy import select

from app.extensions import db
from app.models import Card, Deck, Lesson, Level, UserCardProgress

ROOT = Path(__file__).resolve().parents[2]
CONTENT = ROOT / "content"

# Phase 4/5 lock: all current prototype lessons + decks → A1.
DEFAULT_CONTENT_LEVEL_ID = "a1"
DEFAULT_LESSON_LEVEL_ID = DEFAULT_CONTENT_LEVEL_ID
DEFAULT_DECK_LEVEL_ID = DEFAULT_CONTENT_LEVEL_ID

# Stable ordering for hub display.
DECK_SORT_ORDER = {
    "core_verbs": 1,
    "starter": 2,
    "everyday": 3,
    "days_months": 4,
    "travel": 5,
    "family": 6,
    "home_daily": 7,
    "social_phrases": 8,
    "shopping": 9,
    "health": 10,
    "admin": 11,
    "work": 12,
    "leisure": 13,
    "education": 14,
    "signs": 15,
}


def seed_levels() -> int:
    """Upsert rows from content/levels.json. Returns number of level rows."""
    path = CONTENT / "levels.json"
    rows = json.loads(path.read_text(encoding="utf-8"))
    for row in rows:
        level = db.session.get(Level, row["id"])
        if level is None:
            level = Level(id=row["id"])
            db.session.add(level)
        level.code = row["code"]
        level.title = row["title"]
        level.sort_order = row["sort_order"]
    db.session.commit()
    return len(rows)


def seed_lessons(level_id: str = DEFAULT_LESSON_LEVEL_ID) -> int:
    """Upsert lessons from content/lessons/*.json into the given level."""
    if db.session.get(Level, level_id) is None:
        raise ValueError(f"Level {level_id!r} missing — seed levels first")

    lesson_dir = CONTENT / "lessons"
    paths = sorted(lesson_dir.glob("*.json"))
    for path in paths:
        raw = json.loads(path.read_text(encoding="utf-8"))
        lesson_id = raw["id"]
        lesson = db.session.get(Lesson, lesson_id)
        if lesson is None:
            lesson = Lesson(id=lesson_id)
            db.session.add(lesson)
        lesson.level_id = level_id
        lesson.slug = raw.get("slug") or lesson_id
        lesson.title = raw["title"]
        lesson.summary = raw.get("summary") or ""
        lesson.sort_order = int(raw.get("order") or raw.get("sort_order") or 0)
        lesson.deck_slug = raw.get("deck")
        sections = list(raw.get("sections") or [])
        practice = list(raw.get("practice") or [])
        # Teach surface never keeps inline exercises.
        sections = [section for section in sections if section.get("type") != "exercise"]
        # Back-compat: if practice missing, lift leftover exercises (shouldn't happen after Phase 9 content).
        if not practice:
            practice = [
                {
                    "id": f"{lesson_id}-ex-{index}",
                    "kind": section.get("kind") or "multiple_choice",
                    "question": section.get("question"),
                    "options": section.get("options") or [],
                    "answer": section.get("answer"),
                    "explanation": section.get("explanation") or "",
                }
                for index, section in enumerate(
                    (section for section in (raw.get("sections") or []) if section.get("type") == "exercise"),
                    start=1,
                )
            ]
        lesson.sections_json = sections
        lesson.practice_json = practice
    db.session.commit()
    return len(paths)


def _deck_slug_from_filename(name: str) -> str:
    # starter_deck.json / family_deck.json → starter / family
    return name.split("_deck")[0]


def seed_decks(level_id: str = DEFAULT_DECK_LEVEL_ID) -> tuple[int, int]:
    """Upsert decks + cards from content/decks/*_deck*.json. Returns (decks, cards)."""
    if db.session.get(Level, level_id) is None:
        raise ValueError(f"Level {level_id!r} missing — seed levels first")

    deck_dir = CONTENT / "decks"
    paths = sorted(deck_dir.glob("*_deck*.json"))
    card_count = 0
    seeded_ids: set[str] = set()
    for index, path in enumerate(paths, start=1):
        slug = _deck_slug_from_filename(path.name)
        title = slug.replace("_", " ").title()
        sort_order = DECK_SORT_ORDER.get(slug, 100 + index)
        cards_raw = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(cards_raw, list):
            raise ValueError(f"Deck file must be a JSON list: {path.name}")

        deck = db.session.scalar(select(Deck).where(Deck.slug == slug))
        if deck is None:
            deck = Deck(
                slug=slug,
                level_id=level_id,
                title=title,
                sort_order=sort_order,
            )
            db.session.add(deck)
            db.session.flush()
        else:
            deck.level_id = level_id
            deck.title = title
            deck.sort_order = sort_order

        for raw in cards_raw:
            external_id = raw["id"]
            if external_id in seeded_ids:
                raise ValueError(f"Duplicate card id {external_id!r} in {path.name}")
            seeded_ids.add(external_id)
            forms = raw.get("forms") or []
            if not isinstance(forms, list):
                raise ValueError(f"Card {external_id!r}: forms must be a list")
            card = db.session.scalar(
                select(Card).where(Card.external_id == external_id)
            )
            if card is None:
                card = Card(external_id=external_id)
                db.session.add(card)
            card.deck_id = deck.id
            card.catalan = raw["catalan"]
            card.english = raw["english"]
            card.pronunciation = raw.get("pronunciation") or ""
            card.hint = raw.get("hint") or ""
            card.pos = raw.get("pos") or ""
            card.gender = raw.get("gender")
            card.plural = raw.get("plural")
            card.tags_json = raw.get("tags") or []
            card.forms_json = forms
            card.grammar_lesson_id = raw.get("grammar_lesson_id")
            card_count += 1

    _prune_removed_cards(level_id, seeded_ids)
    db.session.commit()
    return len(paths), card_count


def _prune_removed_cards(level_id: str, seeded_ids: set[str]) -> None:
    """Delete cards no longer in content. Refuse if any still carry progress.

    Removing a studied card silently would lose learner progress; write a data
    migration that merges it into the card that replaces it instead
    (see migrations/versions/e5f6a7b8c9d0_dedupe_vocab_cards.py).
    """
    stale = db.session.scalars(
        select(Card)
        .join(Deck, Deck.id == Card.deck_id)
        .where(Deck.level_id == level_id, Card.external_id.not_in(seeded_ids))
    ).all()
    if not stale:
        return
    stale_ids = [card.id for card in stale]
    studied = db.session.scalars(
        select(Card.external_id)
        .join(UserCardProgress, UserCardProgress.card_id == Card.id)
        .where(Card.id.in_(stale_ids))
        .distinct()
    ).all()
    if studied:
        db.session.rollback()
        raise ValueError(
            "Cards removed from content still have learner progress: "
            f"{', '.join(sorted(studied))}. Merge them with a data migration first."
        )
    for card in stale:
        db.session.delete(card)


def seed_all() -> None:
    seed_levels()
    seed_lessons()
    seed_decks()
