"""Lesson and word counts shown on the level card and the level page."""

from __future__ import annotations

from sqlalchemy import select

from app.extensions import db
from app.models import Card, Deck, UserCardProgress, UserLessonProgress
from app.services.progress import level_progress_counts, progress_summary
from app.services.seed import seed_all


def _counts(**overrides) -> dict:
    counts = {
        "lessons_done": 0,
        "lessons_total": 20,
        "words_learned": 0,
        "words_started": 0,
        "words_total": 500,
    }
    counts.update(overrides)
    return counts


def test_summary_for_fresh_learner_shows_lessons_only():
    assert progress_summary(_counts()) == "0 of 20 lessons"


def test_summary_shows_words_started_before_any_are_learned():
    assert progress_summary(_counts(lessons_done=1, words_started=20)) == (
        "1 of 20 lessons · 20 words started"
    )
    assert progress_summary(_counts(words_started=1)) == "0 of 20 lessons · 1 word started"


def test_summary_prefers_words_learned_once_any_exist():
    summary = progress_summary(_counts(lessons_done=3, words_learned=89, words_started=120))
    assert summary == "3 of 20 lessons · 89 words learned"
    assert progress_summary(_counts(words_learned=1, words_started=5)).endswith("1 word learned")


def test_summary_without_lessons():
    assert progress_summary(_counts(lessons_total=0, words_started=4)) == "4 words started"
    assert progress_summary(_counts(lessons_total=0)) == ""


def _register(client, handle: str = "counter"):
    response = client.post(
        "/api/auth/register",
        json={"handle": handle, "email": f"{handle}@example.com", "password": "password1"},
    )
    assert response.status_code == 201
    return response.get_json()


def _give_progress(user_id: int) -> None:
    db.session.add(
        UserLessonProgress(
            user_id=user_id,
            lesson_id="noun-gender",
            completed=True,
            exercises_correct=1,
            exercises_total=1,
        )
    )
    cards = db.session.scalars(
        select(Card).join(Deck, Deck.id == Card.deck_id).where(Deck.level_id == "a1").limit(6)
    ).all()
    # Seen 0..5, shaped like production rows: 3 of them are retired (seen >= 3).
    for seen, card in enumerate(cards):
        db.session.add(UserCardProgress(user_id=user_id, card_id=card.id, seen=seen))
    db.session.commit()


def test_level_progress_counts_from_db(migrated_app, migrated_client):
    with migrated_app.app_context():
        seed_all()
    body = _register(migrated_client)
    with migrated_app.app_context():
        _give_progress(body["id"])
        counts = level_progress_counts(body["id"], "a1")
        assert counts["lessons_done"] == 1
        assert counts["lessons_total"] == 20
        assert counts["words_learned"] == 3
        assert counts["words_started"] == 5
        assert counts["words_total"] > 100
        # Other levels and other users are not counted.
        assert level_progress_counts(body["id"], "a2")["lessons_done"] == 0


def test_levels_and_level_page_show_counts(migrated_app, migrated_client):
    with migrated_app.app_context():
        seed_all()
    body = _register(migrated_client)

    page = migrated_client.get("/levels").get_data(as_text=True)
    assert '<p class="level-tile__counts">0 of 20 lessons</p>' in page
    assert "%" not in page.split('class="level-tile__meta"')[1].split("</p>")[0]

    with migrated_app.app_context():
        _give_progress(body["id"])

    page = migrated_client.get("/levels").get_data(as_text=True)
    assert '<p class="level-tile__counts">1 of 20 lessons · 3 words learned</p>' in page
    # Placeholder levels have no counts line.
    assert page.count("level-tile__counts") == 1

    level_page = migrated_client.get("/levels/a1").get_data(as_text=True)
    assert "Beginner · 1 of 20 lessons · 3 words learned" in level_page
    assert "% complete" not in level_page
