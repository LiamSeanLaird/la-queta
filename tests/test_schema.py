"""Phase 1 — schema & migrations."""

from __future__ import annotations

import pytest
from flask_migrate import upgrade
from sqlalchemy import inspect, select
from sqlalchemy.exc import IntegrityError

from app.extensions import db
from app.models import (
    Card,
    Deck,
    Lesson,
    Level,
    User,
    UserCardProgress,
    UserLessonProgress,
)


@pytest.fixture
def migrated_app(app):
    with app.app_context():
        upgrade()
        yield app


def test_upgrade_creates_expected_tables(migrated_app):
    with migrated_app.app_context():
        names = set(inspect(db.engine).get_table_names())
    expected = {
        "users",
        "levels",
        "lessons",
        "decks",
        "cards",
        "user_lesson_progress",
        "user_card_progress",
        "alembic_version",
    }
    assert expected <= names


def test_user_handle_is_unique(migrated_app):
    with migrated_app.app_context():
        db.session.add(User(handle="liam"))
        db.session.commit()
        db.session.add(User(handle="liam"))
        with pytest.raises(IntegrityError):
            db.session.commit()
        db.session.rollback()


def test_lesson_slug_is_unique(migrated_app):
    with migrated_app.app_context():
        db.session.add(Level(id="a1", code="A1", title="Beginner", sort_order=1))
        db.session.add(
            Lesson(
                id="noun-gender",
                level_id="a1",
                slug="noun-gender",
                title="Noun Gender",
                summary="…",
                sort_order=1,
                sections_json=[],
            )
        )
        db.session.commit()
        db.session.add(
            Lesson(
                id="noun-gender-2",
                level_id="a1",
                slug="noun-gender",
                title="Dup",
                summary="",
                sort_order=2,
                sections_json=[],
            )
        )
        with pytest.raises(IntegrityError):
            db.session.commit()
        db.session.rollback()


def test_card_external_id_is_unique(migrated_app):
    with migrated_app.app_context():
        db.session.add(Level(id="a1", code="A1", title="Beginner", sort_order=1))
        db.session.add(Deck(level_id="a1", slug="starter", title="Starter", sort_order=1))
        db.session.flush()
        deck_id = db.session.scalar(select(Deck.id).where(Deck.slug == "starter"))
        db.session.add(
            Card(
                deck_id=deck_id,
                external_id="greet_001",
                catalan="Bon dia",
                english="Good morning",
            )
        )
        db.session.commit()
        db.session.add(
            Card(
                deck_id=deck_id,
                external_id="greet_001",
                catalan="Dup",
                english="Dup",
            )
        )
        with pytest.raises(IntegrityError):
            db.session.commit()
        db.session.rollback()


def test_user_lesson_progress_unique_per_user(migrated_app):
    with migrated_app.app_context():
        db.session.add(Level(id="a1", code="A1", title="Beginner", sort_order=1))
        db.session.add(
            Lesson(
                id="noun-gender",
                level_id="a1",
                slug="noun-gender",
                title="Noun Gender",
                summary="",
                sort_order=1,
                sections_json=[],
            )
        )
        db.session.add(User(handle="liam"))
        db.session.commit()
        user_id = db.session.scalar(select(User.id).where(User.handle == "liam"))
        db.session.add(
            UserLessonProgress(
                user_id=user_id,
                lesson_id="noun-gender",
                completed=True,
                exercises_correct=3,
                exercises_total=3,
            )
        )
        db.session.commit()
        db.session.add(
            UserLessonProgress(
                user_id=user_id,
                lesson_id="noun-gender",
                completed=False,
                exercises_correct=0,
                exercises_total=0,
            )
        )
        with pytest.raises(IntegrityError):
            db.session.commit()
        db.session.rollback()


def test_user_card_progress_unique_per_user(migrated_app):
    with migrated_app.app_context():
        db.session.add(Level(id="a1", code="A1", title="Beginner", sort_order=1))
        db.session.add(Deck(level_id="a1", slug="starter", title="Starter", sort_order=1))
        db.session.flush()
        deck_id = db.session.scalar(select(Deck.id).where(Deck.slug == "starter"))
        db.session.add(
            Card(
                deck_id=deck_id,
                external_id="greet_001",
                catalan="Bon dia",
                english="Good morning",
            )
        )
        db.session.add(User(handle="liam"))
        db.session.commit()
        user_id = db.session.scalar(select(User.id).where(User.handle == "liam"))
        card_id = db.session.scalar(select(Card.id).where(Card.external_id == "greet_001"))
        db.session.add(UserCardProgress(user_id=user_id, card_id=card_id, seen=1))
        db.session.commit()
        db.session.add(UserCardProgress(user_id=user_id, card_id=card_id, seen=2))
        with pytest.raises(IntegrityError):
            db.session.commit()
        db.session.rollback()
