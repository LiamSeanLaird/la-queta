"""A progress label and its bar sit close together as one unit.

They used to be separate children of the lesson practice panel's .stack-lg
(2rem gap), the study page's .stack-lg and the deck page's .stack (1rem gap), so 'Item 1 of 13' floated
far above the bar it describes.
"""

import re
from pathlib import Path

from app.services.seed import seed_all

CSS = (Path(__file__).resolve().parents[1] / "static" / "app.css").read_text()


def _rule(selector: str) -> str:
    match = re.search(r"(?m)^" + re.escape(selector) + r"\s*\{([^}]*)\}", CSS)
    assert match, f"no rule for {selector}"
    return match.group(1)


def _assert_meta_and_bar_grouped(page: str) -> None:
    group = page.index('class="progress-group"')
    meta = page.index('class="progress-meta"')
    bar = page.index('class="progress"')
    assert group < meta < bar
    # Nothing closes the group between its opening tag and the bar.
    between = page[group:bar]
    assert between.count("<div") - 1 == between.count("</div>")


def test_progress_group_has_a_small_gap():
    rule = _rule(".progress-group")
    assert "display: flex" in rule
    assert "flex-direction: column" in rule
    assert "gap: 0.5rem" in rule


def test_lesson_practice_deck_and_study_pages_group_label_with_bar(
    migrated_app, migrated_client
):
    with migrated_app.app_context():
        seed_all()
    response = migrated_client.post(
        "/api/auth/register",
        json={
            "handle": "grouper",
            "email": "grouper@example.com",
            "password": "password1",
        },
    )
    assert response.status_code == 201

    _assert_meta_and_bar_grouped(
        migrated_client.get("/lessons/noun-gender?tab=practice").get_data(as_text=True)
    )
    _assert_meta_and_bar_grouped(
        migrated_client.get("/decks/everyday").get_data(as_text=True)
    )
    # study.html serves both deck study and daily review.
    _assert_meta_and_bar_grouped(
        migrated_client.get("/decks/everyday/study").get_data(as_text=True)
    )
