"""The study page ends on a 'Session complete' panel instead of redirecting.

study.js used to send the learner straight back to the deck page (or the vocab
tab) after the last card, so a learner who had just gone through 23 cards
landed on '22 left' with no sign the session had counted.
"""

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
