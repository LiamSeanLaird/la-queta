"""Phase 3 — levels seed, completeness, API."""

from __future__ import annotations

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
from app.services.progress import level_completeness_pct
from app.services.seed import seed_levels


def _register(client, handle: str = "liam"):
    response = client.post("/api/auth/register", json={"handle": handle})
    assert response.status_code == 201
    return response.get_json()


def test_seed_levels_is_idempotent(migrated_app):
    with migrated_app.app_context():
        assert seed_levels() >= 2
        assert seed_levels() >= 2
        from sqlalchemy import select

        levels = db.session.scalars(select(Level).order_by(Level.sort_order)).all()
        assert [level.id for level in levels] == ["a1", "a2"]
        assert [level.code for level in levels] == ["A1", "A2"]


def test_levels_requires_auth(migrated_client):
    response = migrated_client.get("/api/levels")
    assert response.status_code == 401


def test_levels_lists_a1_a2_with_zero_pct(migrated_app, migrated_client):
    with migrated_app.app_context():
        seed_levels()
    _register(migrated_client)
    response = migrated_client.get("/api/levels")
    assert response.status_code == 200
    levels = response.get_json()["levels"]
    assert [row["id"] for row in levels] == ["a1", "a2"]
    assert all(row["complete_pct"] == 0 for row in levels)
    assert all(row["is_current"] is False for row in levels)


def test_select_level_sets_current(migrated_app, migrated_client):
    with migrated_app.app_context():
        seed_levels()
    _register(migrated_client)
    response = migrated_client.post("/api/levels/a1/select")
    assert response.status_code == 200
    assert response.get_json()["current_level_id"] == "a1"

    levels = migrated_client.get("/api/levels").get_json()["levels"]
    by_id = {row["id"]: row for row in levels}
    assert by_id["a1"]["is_current"] is True
    assert by_id["a2"]["is_current"] is False


def test_select_unknown_level_404(migrated_app, migrated_client):
    with migrated_app.app_context():
        seed_levels()
    _register(migrated_client)
    response = migrated_client.post("/api/levels/b1/select")
    assert response.status_code == 404


def test_completeness_lessons_only_when_no_vocab(migrated_app):
    with migrated_app.app_context():
        seed_levels()
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
        user = User(handle="prog")
        db.session.add(user)
        db.session.commit()
        db.session.add(
            UserLessonProgress(
                user_id=user.id,
                lesson_id="noun-gender",
                completed=True,
                exercises_correct=1,
                exercises_total=1,
            )
        )
        db.session.commit()
        assert level_completeness_pct(user.id, "a1") == 100
        assert level_completeness_pct(user.id, "a2") == 0


def test_completeness_weights_lessons_and_vocab(migrated_app):
    with migrated_app.app_context():
        seed_levels()
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
        deck = Deck(level_id="a1", slug="starter", title="Starter", sort_order=1)
        db.session.add(deck)
        db.session.flush()
        db.session.add(
            Card(
                deck_id=deck.id,
                external_id="greet_001",
                catalan="Bon dia",
                english="Good morning",
            )
        )
        user = User(handle="weighted")
        db.session.add(user)
        db.session.commit()
        # 1/1 lessons done, 0/1 vocab retired → 70%
        db.session.add(
            UserLessonProgress(
                user_id=user.id,
                lesson_id="noun-gender",
                completed=True,
                exercises_correct=1,
                exercises_total=1,
            )
        )
        db.session.commit()
        assert level_completeness_pct(user.id, "a1") == 70

        from sqlalchemy import select

        card = db.session.scalar(select(Card).where(Card.external_id == "greet_001"))
        db.session.add(UserCardProgress(user_id=user.id, card_id=card.id, seen=3))
        db.session.commit()
        assert level_completeness_pct(user.id, "a1") == 100
