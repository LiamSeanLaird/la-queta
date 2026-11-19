"""The deck page links to the lessons that teach the deck's grammar.

Before, /decks/<slug> only offered Study and Browse, so a learner who opened
vocab from the Vocab tab had no way to see which lesson it belonged to.
"""

import html
import re

from app.services.seed import seed_all


def _lesson_rows(client, slug: str) -> list[tuple[str, str, str]]:
    page = client.get(f"/decks/{slug}").get_data(as_text=True)
    section = re.search(
        r'<div class="stack" id="deck-lessons">(.*?)\n  </div>\n', page, re.S
    )
    assert section, f"no lessons section on /decks/{slug}"
    rows = re.findall(
        r'href="/lessons/([\w-]+)">.*?list-row__title">([^<]+)</p>'
        r'.*?(badge--todo|aria-label="Done, \d of 3 stars")',
        section.group(1),
        re.S,
    )
    return [
        (lesson_id, html.unescape(title), "todo" if "todo" in status else "done")
        for lesson_id, title, status in rows
    ]


def test_deck_page_lists_its_lessons_with_progress(migrated_app, migrated_client):
    with migrated_app.app_context():
        seed_all()
    response = migrated_client.post(
        "/api/auth/register",
        json={
            "handle": "decklinks",
            "email": "decklinks@example.com",
            "password": "password1",
        },
    )
    assert response.status_code == 201

    page = migrated_client.get("/decks/signs").get_data(as_text=True)
    assert "Lesson for this deck" in page
    assert _lesson_rows(migrated_client, "signs") == [
        ("signs-messages", "Signs & Messages", "todo")
    ]

    # food_drink belongs to two lessons, listed in lesson order.
    page = migrated_client.get("/decks/food_drink").get_data(as_text=True)
    assert "Lessons for this deck" in page
    assert _lesson_rows(migrated_client, "food_drink") == [
        ("definite-articles", "Definite Articles", "todo"),
        ("food-cafe", "Food & Café", "todo"),
    ]

    total = len(migrated_client.get("/api/lessons/food-cafe").get_json()["practice"])
    response = migrated_client.post(
        "/api/lessons/food-cafe/complete",
        json={"exercises_correct": total, "exercises_total": total},
    )
    assert response.status_code == 200
    assert _lesson_rows(migrated_client, "food_drink") == [
        ("definite-articles", "Definite Articles", "todo"),
        ("food-cafe", "Food & Café", "done"),
    ]
