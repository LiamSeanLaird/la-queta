"""The lesson test in a real browser: missed questions come back, and the score.

Runs the app on a local port and drives lesson 1's test in headless Chromium.
Skipped when Playwright has no Chromium to launch (set PLAYWRIGHT_CHROMIUM to
use a specific binary).
"""

from __future__ import annotations

import glob
import json
import os
import threading
import uuid

import pytest
from sqlalchemy import select
from werkzeug.serving import make_server

from app import create_app
from app.extensions import db
from app.models import Lesson
from app.services.seed import seed_all

playwright_api = pytest.importorskip("playwright.sync_api")

LESSON_ID = "noun-gender"


def _chromium_path() -> str | None:
    explicit = os.environ.get("PLAYWRIGHT_CHROMIUM")
    if explicit:
        return explicit
    pattern = os.path.expanduser(
        "~/Library/Caches/ms-playwright/chromium-*/chrome-mac*/*.app/Contents/MacOS/*"
    )
    matches = sorted(glob.glob(pattern))
    return matches[-1] if matches else None


@pytest.fixture
def live_app(tmp_path):
    from flask_migrate import upgrade

    app = create_app(
        {
            "TESTING": True,
            # A file database, so the server thread and the test share it.
            "SQLALCHEMY_DATABASE_URI": f"sqlite:///{tmp_path / 'browser.db'}",
            "PUBLIC_BASE_URL": "",
        }
    )
    with app.app_context():
        upgrade()
        seed_all()
        lesson = db.session.scalar(select(Lesson).where(Lesson.id == LESSON_ID))
        items = list(lesson.practice_json)
    server = make_server("127.0.0.1", 0, app, threaded=True)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield app, f"http://127.0.0.1:{server.server_port}", items
    server.shutdown()
    thread.join()


@pytest.fixture
def browser():
    with playwright_api.sync_playwright() as p:
        try:
            chromium = p.chromium.launch(executable_path=_chromium_path())
        except Exception as exc:  # no browser installed (for example in CI)
            pytest.skip(f"Chromium not available: {exc}")
        yield chromium
        chromium.close()


def _accepted(item: dict) -> list[str]:
    if item.get("answers"):
        return [str(a) for a in item["answers"]]
    return [str(item["answer"])] if item.get("answer") is not None else []


def _answer(page, item: dict, right: bool) -> None:
    """Answer the question on screen, right or wrong, and wait for what follows."""
    root = page.locator("#practice-item")
    kind = item["kind"]
    if kind == "speak":
        assert right, "speak items are always right"
        root.get_by_role("button", name="I said it").click()
        return
    options = item.get("options") or []
    if options:
        accepted = {a.lower() for a in _accepted(item)}
        pick = next(o for o in options if (o.lower() in accepted) == right)
        root.get_by_role("button", name=pick, exact=True).click()
    else:
        root.locator("input").fill(_accepted(item)[0] if right else "zzz")
        root.get_by_role("button", name="Check").click()
    if not right:
        expect = playwright_api.expect
        expect(root.get_by_text("This question comes back at the end.")).to_be_visible()
        root.get_by_role("button", name="Continue").click()


def _take_test(page, items: list[dict], miss: set[int]) -> list[str]:
    """Answer every question, getting the `miss` indexes wrong once.

    Returns the progress line shown for each question, in order.
    """
    page.get_by_role("button", name="Start the test").click()
    order = list(range(len(items))) + sorted(miss)
    progress = []
    expect = playwright_api.expect
    for step, index in enumerate(order):
        if step:
            # Wait for the next question to replace the last one.
            expect(page.locator("#practice-progress-text")).not_to_have_text(progress[-1])
        progress.append(page.locator("#practice-progress-text").inner_text())
        _answer(page, items[index], right=(step >= len(items) or index not in miss))
    expect(page.locator("#practice-done")).to_be_visible()
    return progress


def test_missed_questions_come_back_and_score_first_tries(live_app, browser):
    app, base, items = live_app
    total = len(items)
    # A multiple choice, a cloze, a type-in and a listening question.
    miss = {0, 4, 8, 11}
    page = browser.new_page()
    errors = []
    page.on("pageerror", lambda exc: errors.append(str(exc)))
    page.goto(f"{base}/lessons/{LESSON_ID}?tab=test")

    progress = _take_test(page, items, miss)

    # The first pass counts every question; the missed ones come back after.
    assert progress[:total] == [f"Question {n} of {total}" for n in range(1, total + 1)]
    assert progress[total:] == [
        f"Missed question - {left} left" for left in range(len(miss), 0, -1)
    ]
    first_try = total - len(miss)
    assert page.locator("#test-score-text").inner_text() == (
        f"{first_try} of {total} right first time"
    )
    # 10 of 14 is under 75%, so 1 star, and the retry link shows.
    stars = page.locator("#test-score-stars")
    assert stars.get_attribute("aria-label") == "1 of 3 stars"
    assert stars.locator(".is-earned").count() == 1
    assert page.locator("#test-retry").is_visible()
    # Logged out: the score waits in sessionStorage for sign-up.
    pending = json.loads(
        page.evaluate("sessionStorage.getItem('laqueta.pendingCompletion')")
    )
    assert pending == {
        "lesson_id": LESSON_ID,
        "exercises_correct": total,
        "exercises_total": total,
        "first_try_correct": first_try,
    }
    assert errors == []


def test_logged_in_score_is_saved_and_a_worse_retake_keeps_the_best(live_app, browser):
    app, base, items = live_app
    total = len(items)
    context = browser.new_context()
    page = context.new_page()
    page.goto(f"{base}/signup")
    handle = f"t{uuid.uuid4().hex[:8]}"
    page.evaluate(
        """async ([handle]) => {
            const r = await fetch('/api/auth/register', {
              method: 'POST',
              headers: {'Content-Type': 'application/json'},
              body: JSON.stringify({handle, email: handle + '@example.com', password: 'password123'}),
            });
            if (!r.ok) throw new Error('register failed');
        }""",
        [handle],
    )

    page.goto(f"{base}/lessons/{LESSON_ID}?tab=test")
    _take_test(page, items, miss=set())
    assert page.locator("#test-score-text").inner_text() == f"{total} of {total} right first time"
    assert page.locator("#test-score-stars").get_attribute("aria-label") == "3 of 3 stars"
    assert not page.locator("#test-retry").is_visible()
    playwright_api.expect(page.get_by_text("Lesson complete - well done.")).to_be_visible()

    def saved():
        return page.evaluate(
            f"fetch('/api/lessons/{LESSON_ID}').then((r) => r.json())"
        )

    page.wait_for_function(
        f"fetch('/api/lessons/{LESSON_ID}').then((r) => r.json()).then((b) => b.best_first_try === {total})"
    )
    assert saved()["stars"] == 3

    # A retake with misses shows its own score, but the saved best stays.
    page.goto(f"{base}/lessons/{LESSON_ID}?tab=test")
    with page.expect_response(lambda r: r.url.endswith("/complete")) as retake:
        _take_test(page, items, miss={1})
    assert retake.value.ok
    assert page.locator("#test-score-text").inner_text() == (
        f"{total - 1} of {total} right first time"
    )
    assert page.locator("#test-score-stars").get_attribute("aria-label") == "2 of 3 stars"
    assert page.locator("#test-retry").is_visible()
    # The goal dialog is only for a first completion.
    assert not page.locator("#goal-unlock-dialog").is_visible()
    body = saved()
    assert body["best_first_try"] == total
    assert body["stars"] == 3
    context.close()


def test_logged_out_score_is_saved_on_sign_up(live_app, browser):
    app, base, items = live_app
    total = len(items)
    context = browser.new_context()
    page = context.new_page()
    page.goto(f"{base}/lessons/{LESSON_ID}?tab=test")
    _take_test(page, items, miss={2})

    page.locator("#practice-done").get_by_role("link", name="Create a free account").click()
    handle = f"t{uuid.uuid4().hex[:8]}"
    page.fill("#handle-input", handle)
    page.fill("#reg-email-input", f"{handle}@example.com")
    page.fill("#reg-password-input", "password123")
    page.get_by_role("button", name="Create account").click()

    page.wait_for_url(f"**/lessons/{LESSON_ID}?saved=1&finished=1")
    body = page.evaluate(f"fetch('/api/lessons/{LESSON_ID}').then((r) => r.json())")
    assert body["completed"] is True
    assert body["best_first_try"] == total - 1
    assert body["stars"] == 2
    context.close()
