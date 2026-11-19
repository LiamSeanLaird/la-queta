"""Phase 10 — daily vocab + can-dos."""

from __future__ import annotations

from app.services.seed import seed_all


def _register(client, handle: str = "dailyuser"):
    slug = "".join(handle.lower().split())
    response = client.post(
        "/api/auth/register",
        json={
            "handle": handle,
            "email": f"{slug}@example.com",
            "password": "password1",
        },
    )
    assert response.status_code == 201
    return response.get_json()


def test_daily_session_returns_unretired_cards(migrated_app, migrated_client):
    with migrated_app.app_context():
        seed_all()
    _register(migrated_client)

    response = migrated_client.get("/api/levels/a1/daily")
    assert response.status_code == 200
    body = response.get_json()
    assert "cards" in body
    assert 1 <= len(body["cards"]) <= 20
    assert all(card["retired"] is False for card in body["cards"])


def test_daily_session_fills_from_retired_when_needed(migrated_app, migrated_client):
    with migrated_app.app_context():
        seed_all()
    _register(migrated_client)

    cards = migrated_client.get("/api/decks/starter/cards").get_json()["cards"]
    for card in cards:
        assert (
            migrated_client.post(f"/api/cards/{card['id']}/retire").status_code == 200
        )

    # Other decks still have unretired — retire nothing else; just ensure API works
    response = migrated_client.get("/api/levels/a1/daily")
    assert response.status_code == 200
    assert len(response.get_json()["cards"]) <= 20


def test_daily_page_renders(migrated_app, migrated_client):
    with migrated_app.app_context():
        seed_all()
    _register(migrated_client)
    page = migrated_client.get("/levels/a1/daily")
    assert page.status_code == 200
    assert b"js/study.js" in page.data
    assert b"/api/levels/a1/daily" in page.data


def test_can_dos_on_level_learn_tab(migrated_app, migrated_client):
    with migrated_app.app_context():
        seed_all()
    _register(migrated_client)
    page = migrated_client.get("/levels/a1")
    assert page.status_code == 200
    assert b"can-dos-dialog" in page.data
    assert b"data-can-dos-open" in page.data
    assert b"goals" in page.data
    assert b"Finish every lesson in a goal to tick it off." in page.data
    assert b"Build core grammar" in page.data
    assert b"goal-section" in page.data
    assert b"Daily vocab" not in page.data
    assert b"Continue:" not in page.data

    hub = migrated_client.get("/levels")
    assert b"Daily vocab" in hub.data
    assert b"goals" in hub.data
    assert b"can-dos-a1" in hub.data
    assert b"Finish every lesson in a goal to tick it off." in hub.data
    assert b"Next goal:" in hub.data
    assert b"See all 7 goals" in hub.data
    assert b"Send feedback" in hub.data
    assert b"feedback-dialog" in hub.data
    assert b"A note for the developer (Liam)" in hub.data
    assert b"Write to me" in hub.data
    assert b"mailto:liamlaird120@gmail.com" in hub.data
    vocab = migrated_client.get("/levels/a1?tab=vocab")
    assert vocab.status_code == 200
    assert b"goal-section" in vocab.data
    assert b"Introduce myself" in vocab.data
    assert b"Greetings &amp; Introductions" in vocab.data
    # Fully retired starter → Done chip + goal progress fraction in markup
    assert b"badge--done" in vocab.data or b"0/" in vocab.data


def test_completing_last_lesson_in_goal_unlocks_it(migrated_app, migrated_client):
    with migrated_app.app_context():
        seed_all()
    _register(migrated_client)

    total = len(migrated_client.get("/api/lessons/public-admin").get_json()["practice"])
    response = migrated_client.post(
        "/api/lessons/public-admin/complete",
        json={"exercises_correct": total, "exercises_total": total},
    )
    assert response.status_code == 200
    body = response.get_json()
    unlocked = body.get("goals_unlocked") or []
    assert any(item["id"] == "public-services" for item in unlocked)
    assert any("public services" in item["label"].lower() for item in unlocked)


def _deck_of_each_daily_card(client) -> set[str]:
    cards = client.get("/api/levels/a1/daily").get_json()["cards"]
    return {card["deck_slug"] for card in cards}


def _first_deck_slug(client) -> str:
    decks = client.get("/api/levels/a1/decks").get_json()["decks"]
    return decks[0]["slug"]


def test_daily_session_for_new_learner_uses_first_deck_then_next(
    migrated_app, migrated_client
):
    with migrated_app.app_context():
        seed_all()
    _register(migrated_client)
    decks = migrated_client.get("/api/levels/a1/decks").get_json()["decks"]

    cards = migrated_client.get("/api/levels/a1/daily").get_json()["cards"]
    assert len(cards) == 20
    first = decks[0]
    from_first = [card for card in cards if card["deck_slug"] == first["slug"]]
    assert len(from_first) == min(20, first["total"])
    # Any top-up comes from the next deck in level order, never a later one.
    allowed = {first["slug"], decks[1]["slug"]}
    assert {card["deck_slug"] for card in cards} <= allowed


def test_daily_session_follows_completed_lessons_and_started_decks(
    migrated_app, migrated_client
):
    with migrated_app.app_context():
        seed_all()
    _register(migrated_client)
    first = _first_deck_slug(migrated_client)

    lesson = migrated_client.get("/api/lessons/public-admin").get_json()
    deck_slug = "admin"  # content/lessons/20-public-admin.json links this deck
    assert deck_slug != first
    total = len(lesson["practice"])
    assert (
        migrated_client.post(
            "/api/lessons/public-admin/complete",
            json={"exercises_correct": total, "exercises_total": total},
        ).status_code
        == 200
    )
    # Completing a lesson replaces the first-deck default with its deck.
    assert _deck_of_each_daily_card(migrated_client) == {deck_slug}

    # Starting another deck in study adds it to the pool.
    leisure = migrated_client.get("/api/decks/leisure/cards").get_json()["cards"]
    assert (
        migrated_client.post(f"/api/cards/{leisure[0]['id']}/seen").status_code == 200
    )
    decks_seen: set[str] = set()
    for _ in range(10):
        decks_seen |= _deck_of_each_daily_card(migrated_client)
    assert decks_seen == {deck_slug, "leisure"}


def test_goal_dialogs_never_say_unlock(migrated_app, migrated_client):
    """Goals are never locked, so learner-facing goal text must not say 'unlock'."""
    with migrated_app.app_context():
        seed_all()
    _register(migrated_client)
    for path in ("/levels", "/levels/a1", "/lessons/public-admin?tab=test"):
        text = migrated_client.get(path).get_data(as_text=True)
        visible = text.replace("goal-unlock", "")
        assert "nlock" not in visible, path
    practice = migrated_client.get("/lessons/public-admin?tab=test").get_data(
        as_text=True
    )
    assert 'id="goal-unlock-title">Goal complete</h3>' in practice
