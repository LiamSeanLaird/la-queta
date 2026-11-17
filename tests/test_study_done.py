"""The study page ends on a 'Session complete' panel instead of redirecting.

study.js used to send the learner straight back to the deck page (or the vocab
tab) after the last card, so a learner who had just gone through 23 cards
landed on '22 left' with no sign the session had counted.
"""

import html
import re
from pathlib import Path

from app.services.seed import seed_all

STUDY_JS = (
    Path(__file__).resolve().parents[1] / "static" / "js" / "study.js"
).read_text()


def _done_panel(page: str) -> str:
    match = re.search(
        r'<div class="stack" id="study-done" hidden>(.*?)\n  </div>', page, re.S
    )
    assert match, "no hidden study-done panel"
    return match.group(1)


def test_study_pages_end_on_a_done_panel(migrated_app, migrated_client):
    with migrated_app.app_context():
        seed_all()
    response = migrated_client.post(
        "/api/auth/register",
        json={
            "handle": "finisher",
            "email": "finisher@example.com",
            "password": "password1",
        },
    )
    assert response.status_code == 201

    deck = _done_panel(migrated_client.get("/decks/signs/study").get_data(as_text=True))
    assert 'href="/decks/signs/study" id="study-again"' in deck
    assert 'href="/decks/signs" id="study-exit">Back to deck</a>' in deck
    assert "Unretire the deck to study it again." in deck

    daily = _done_panel(migrated_client.get("/levels/a1/daily").get_data(as_text=True))
    assert 'href="/levels/a1/daily" id="study-again"' in daily
    assert 'href="/levels/a1?tab=vocab" id="study-exit">Back to vocab</a>' in daily
    assert "There are no cards to review right now." in daily


def test_study_js_shows_the_panel_instead_of_redirecting():
    assert "location.assign" not in STUDY_JS
    assert "location.href" not in STUDY_JS
    assert "Session complete" in STUDY_JS


def _function_body(name: str) -> str:
    match = re.search(rf"async function {name}\(\) {{\n(.*?)\n  }}\n", STUDY_JS, re.S)
    assert match, f"no {name} in study.js"
    return match.group(1)


def test_study_js_counts_each_card_once_per_session():
    """Going Back and stepping through a card again must not post /seen twice.

    Before, Back then Next posted /seen again, so one session could take a
    card two thirds of the way to retirement.
    """
    advance = _function_body("advanceSeen")
    guard = advance.index("countedThisSession.has(card.id)")
    assert guard < advance.index("/seen"), "seen POST must come after the guard"
    assert "countedThisSession.add(card.id)" in advance
    assert "countedThisSession.add(card.id)" in _function_body("retireCurrent")


def _next_lesson_link(client, path: str) -> str | None:
    panel = _done_panel(client.get(path).get_data(as_text=True))
    match = re.search(
        r'href="/lessons/([\w-]+)" id="study-next-lesson">Next lesson: ([^<]+)</a>',
        panel,
    )
    return f"{match.group(1)} | {html.unescape(match.group(2))}" if match else None


def _complete(client, lesson_id: str) -> None:
    total = len(client.get(f"/api/lessons/{lesson_id}").get_json()["practice"])
    response = client.post(
        f"/api/lessons/{lesson_id}/complete",
        json={"exercises_correct": total, "exercises_total": total},
    )
    assert response.status_code == 200


def test_done_panel_offers_the_next_lesson(migrated_app, migrated_client):
    """After vocab, the done panel points back into the lesson path.

    Before, the only ways out of a finished session were 'Study again' and
    'Back to deck', so a learner who did lesson then vocab had to find the
    next lesson on the Learn tab themselves.
    """
    with migrated_app.app_context():
        seed_all()
    response = migrated_client.post(
        "/api/auth/register",
        json={"handle": "pathfinder", "email": "path@example.com", "password": "password1"},
    )
    assert response.status_code == 201

    # food_drink belongs to Definite Articles (2) and Food & Café (11).
    # Their unfinished lesson comes first, so vocab-first learners still meet it.
    assert _next_lesson_link(migrated_client, "/decks/food_drink/study") == (
        "definite-articles | Definite Articles"
    )
    _complete(migrated_client, "definite-articles")
    assert _next_lesson_link(migrated_client, "/decks/food_drink/study") == (
        "food-cafe | Food & Café"
    )
    _complete(migrated_client, "food-cafe")
    # With both done, it is the next unfinished lesson after Food & Café.
    assert _next_lesson_link(migrated_client, "/decks/food_drink/study") == (
        "shopping | Shopping"
    )

    # Daily review offers the level's first unfinished lesson.
    assert _next_lesson_link(migrated_client, "/levels/a1/daily") == (
        "noun-gender | Noun Gender"
    )
    panel = _done_panel(migrated_client.get("/levels/a1/daily").get_data(as_text=True))
    assert 'class="btn btn--ghost btn--block" href="/levels/a1?tab=vocab" id="study-exit"' in panel


def test_study_js_promotes_next_lesson_when_nothing_is_left():
    assert 'getElementById("study-next-lesson")' in STUDY_JS
    assert 'studyNextLesson.classList.toggle("btn--primary", !canStudyAgain)' in STUDY_JS
