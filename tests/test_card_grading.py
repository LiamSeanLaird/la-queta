"""Spaced repetition: self-grading cards and carrying over existing progress."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
import sqlalchemy as sa
from flask_migrate import downgrade, upgrade
from sqlalchemy import select

from app.extensions import db
from app.models import Card, User, UserCardProgress
from app.services.progress import RETIRED_SEEN
from app.services.seed import seed_all
from app.services.vocab import REVIEW_INTERVALS, grade_card, next_interval

NOW = datetime(2026, 11, 17, 9, 30)


def _register(client, handle: str = "grader") -> dict:
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


def _first_card_id() -> int:
    return db.session.scalar(select(Card.id).order_by(Card.id))


def _progress(user_id: int, card_id: int) -> UserCardProgress:
    return db.session.scalar(
        select(UserCardProgress).where(
            UserCardProgress.user_id == user_id, UserCardProgress.card_id == card_id
        )
    )


@pytest.mark.parametrize(
    ("current", "knew", "expected"),
    [
        (0, True, 1),
        (1, True, 3),
        (3, True, 7),
        (7, True, 14),
        (5, True, 7),  # off-ladder values step to the next rung
        (60, True, 60),  # capped
        (14, False, 0),
        (0, False, 0),
    ],
)
def test_next_interval(current, knew, expected):
    assert next_interval(current, knew) == expected


def test_knew_it_steps_up_and_retires_after_three(migrated_app):
    with migrated_app.app_context():
        seed_all()
        user = User(handle="g", email="g@example.com", password_hash="x")
        db.session.add(user)
        db.session.commit()
        card_id = _first_card_id()

        first = grade_card(user, card_id, "knew", now=NOW)
        assert (first["seen"], first["interval_days"], first["retired"]) == (
            1,
            1,
            False,
        )
        assert first["due_at"] == (NOW + timedelta(days=1)).isoformat()

        grade_card(user, card_id, "knew", now=NOW + timedelta(days=1))
        third = grade_card(user, card_id, "knew", now=NOW + timedelta(days=4))
        assert third["seen"] == RETIRED_SEEN
        assert third["retired"] is True
        assert third["interval_days"] == REVIEW_INTERVALS[2]
        row = _progress(user.id, card_id)
        assert row.due_at == NOW + timedelta(days=4 + 7)
        assert row.last_reviewed_at == NOW + timedelta(days=4)


def test_not_yet_resets_interval_and_never_retires(migrated_app):
    with migrated_app.app_context():
        seed_all()
        user = User(handle="n", email="n@example.com", password_hash="x")
        db.session.add(user)
        db.session.commit()
        card_id = _first_card_id()

        grade_card(user, card_id, "knew", now=NOW)
        grade_card(user, card_id, "knew", now=NOW)
        for _ in range(5):
            result = grade_card(user, card_id, "not_yet", now=NOW)
        assert result["seen"] == 2
        assert result["retired"] is False
        assert result["interval_days"] == 0
        assert _progress(user.id, card_id).due_at == NOW


def test_grade_endpoint(migrated_client, migrated_app):
    with migrated_app.app_context():
        seed_all()
        card_id = _first_card_id()

    assert (
        migrated_client.post(
            f"/api/cards/{card_id}/grade", json={"grade": "knew"}
        ).status_code
        == 401
    )

    body = _register(migrated_client)
    response = migrated_client.post(
        f"/api/cards/{card_id}/grade", json={"grade": "knew"}
    )
    assert response.status_code == 200
    data = response.get_json()
    assert (data["seen"], data["interval_days"]) == (1, 1)

    response = migrated_client.post(
        f"/api/cards/{card_id}/grade", json={"grade": "not_yet"}
    )
    assert response.get_json()["interval_days"] == 0

    for bad in ({"grade": "maybe"}, {}, None):
        response = migrated_client.post(f"/api/cards/{card_id}/grade", json=bad)
        assert response.status_code == 400
    assert (
        migrated_client.post(
            "/api/cards/999999/grade", json={"grade": "knew"}
        ).status_code
        == 404
    )

    with migrated_app.app_context():
        assert _progress(body["id"], card_id).seen == 1


def test_migration_maps_production_seen_values(migrated_app):
    """Rows shaped like production (seen 0 to 5, no schedule) carry over."""
    with migrated_app.app_context():
        seed_all()
        downgrade(revision="b8c9d0e1f2a3")
        conn = db.session.connection()
        conn.execute(
            sa.text(
                "INSERT INTO users (handle, email, password_hash) "
                "VALUES ('prod', 'prod@example.com', 'x')"
            )
        )
        user_id = conn.execute(
            sa.text("SELECT id FROM users WHERE handle = 'prod'")
        ).scalar()
        card_ids = (
            conn.execute(sa.text("SELECT id FROM cards ORDER BY id LIMIT 6"))
            .scalars()
            .all()
        )
        for seen, card_id in enumerate(card_ids):
            conn.execute(
                sa.text(
                    "INSERT INTO user_card_progress (user_id, card_id, seen) "
                    "VALUES (:u, :c, :s)"
                ),
                {"u": user_id, "c": card_id, "s": seen},
            )
        db.session.commit()

        before = datetime.now(UTC).replace(tzinfo=None) - timedelta(seconds=5)
        upgrade()
        db.session.expire_all()

        rows = {
            row.seen: row
            for row in db.session.scalars(
                select(UserCardProgress).where(UserCardProgress.user_id == user_id)
            )
        }
        assert sorted(rows) == [0, 1, 2, 3, 4, 5]
        assert {seen: row.interval_days for seen, row in rows.items()} == {
            0: 0,
            1: 1,
            2: 3,
            3: 7,
            4: 7,
            5: 7,
        }
        assert rows[0].due_at is None
        for seen in range(1, 6):
            assert rows[seen].due_at >= before
            assert rows[seen].last_reviewed_at is None
        # Retired cards stay retired: seen is untouched.
        assert [seen for seen in rows if seen >= RETIRED_SEEN] == [3, 4, 5]

        # Downgrading keeps seen intact.
        downgrade(revision="b8c9d0e1f2a3")
        seen_after = (
            db.session.connection()
            .execute(
                sa.text(
                    "SELECT seen FROM user_card_progress WHERE user_id = :u ORDER BY seen"
                ),
                {"u": user_id},
            )
            .scalars()
            .all()
        )
        assert seen_after == [0, 1, 2, 3, 4, 5]
        upgrade()
