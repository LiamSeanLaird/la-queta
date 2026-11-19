"""Lesson pages are public: logged-out visitors can read every lesson and take its test."""

import json
import re
from html import unescape

from sqlalchemy import select

from app.extensions import db
from app.models import Lesson
from app.services.lessons import get_lesson, list_lessons_for_level
from app.services.progress import lesson_next_steps
from app.services.seed import seed_all


def _lessons(app):
    with app.app_context():
        seed_all()
        rows = db.session.scalars(
            select(Lesson).order_by(Lesson.sort_order, Lesson.id)
        ).all()
        return [
            {
                "id": row.id,
                "title": row.title,
                "first_text": next(
                    s["content"] for s in row.sections_json if s["type"] == "text"
                ),
                "practice": row.practice_json,
            }
            for row in rows
        ]


def _register(client):
    response = client.post(
        "/api/auth/register",
        json={
            "handle": "Visitor",
            "email": "visitor@example.com",
            "password": "password1",
        },
    )
    assert response.status_code == 201


def _text(html: bytes) -> str:
    return unescape(re.sub(r"<[^>]+>", "", html.decode()))


def test_every_lesson_renders_logged_out(migrated_app, migrated_client):
    lessons = _lessons(migrated_app)
    assert len(lessons) == 20
    for lesson in lessons:
        response = migrated_client.get(f"/lessons/{lesson['id']}")
        assert response.status_code == 200, lesson["id"]
        text = _text(response.data)
        assert lesson["title"] in text
        # The Learn tab's opening paragraph is in the HTML a crawler sees.
        assert lesson["first_text"][:40] in text, lesson["id"]


def test_test_tab_renders_logged_out(migrated_app, migrated_client):
    lesson = _lessons(migrated_app)[0]
    response = migrated_client.get(f"/lessons/{lesson['id']}?tab=test")
    assert response.status_code == 200
    html = response.data.decode()
    assert "js/practice.js" in html
    assert 'data-logged-in="false"' in html
    data = re.search(
        r'<script type="application/json" id="practice-data">(.*?)</script>', html, re.S
    )
    assert json.loads(data.group(1)) == lesson["practice"]
    # The completion step asks for an account instead of claiming it was saved.
    assert "Create a free account to save this lesson and your score, and keep going." in html
    assert "Lesson complete - well done." not in html
    assert 'href="/signup">Create a free account</a>' in html
    assert 'href="/signin">Sign in</a>' in html


def test_logged_out_topbar_offers_sign_in(migrated_app, migrated_client):
    lesson = _lessons(migrated_app)[0]
    html = migrated_client.get(f"/lessons/{lesson['id']}").data.decode()
    assert 'class="btn btn--secondary topbar__signin" href="/signin"' in html
    assert 'id="profile-open"' not in html
    assert 'id="profile-dialog"' not in html
    assert "profile-logout" not in html
    # Back and brand go to the public home page, not the logged-in hub.
    assert 'class="topbar__back" href="/"' in html
    assert 'class="brand__link" href="/"' in html


def test_logged_out_completion_post_is_401(migrated_app, migrated_client):
    lesson = _lessons(migrated_app)[0]
    total = len(lesson["practice"])
    response = migrated_client.post(
        f"/api/lessons/{lesson['id']}/complete",
        json={"exercises_correct": total, "exercises_total": total},
    )
    assert response.status_code == 401


def test_unknown_lesson_logged_out_is_a_real_404(migrated_app, migrated_client):
    # A redirect home would read to crawlers as a soft 404.
    _lessons(migrated_app)
    response = migrated_client.get("/lessons/no-such-lesson")
    assert response.status_code == 404
    html = response.data.decode()
    assert "Page not found" in html
    assert '<meta name="robots" content="noindex">' in html
    assert 'rel="canonical"' not in html
    assert len(re.findall(r"<h1\b", html)) == 1
    assert 'href="/"' in html


def test_unknown_lesson_logged_in_still_goes_to_levels(migrated_app, migrated_client):
    _lessons(migrated_app)
    _register(migrated_client)
    response = migrated_client.get("/lessons/no-such-lesson")
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/levels")


def test_unknown_page_is_branded_404(migrated_app, migrated_client):
    response = migrated_client.get("/no-such-page")
    assert response.status_code == 404
    html = response.data.decode()
    assert "Page not found" in html
    assert '<meta name="robots" content="noindex">' in html


def test_unknown_api_route_is_json_404(migrated_app, migrated_client):
    response = migrated_client.get("/api/no-such-route")
    assert response.status_code == 404
    assert response.get_json() == {"error": "Not found"}


def test_logged_in_lesson_page_unchanged(migrated_app, migrated_client):
    lesson = _lessons(migrated_app)[0]
    _register(migrated_client)
    html = migrated_client.get(f"/lessons/{lesson['id']}?tab=test").data.decode()
    assert 'data-logged-in="true"' in html
    assert "Lesson complete - well done." in html
    assert "topbar__signin" not in html
    assert 'id="profile-open"' in html
    assert 'class="topbar__back" href="/levels/a1"' in html


def test_services_logged_out_path(migrated_app):
    lessons = _lessons(migrated_app)
    with migrated_app.app_context():
        listed = list_lessons_for_level(None, "a1")
        assert [row["id"] for row in listed] == [row["id"] for row in lessons]
        assert not any(row["completed"] for row in listed)

        detail = get_lesson(None, lessons[0]["id"])
        assert detail["completed"] is False
        assert detail["exercises_correct"] == 0

        steps = lesson_next_steps(None, lessons[0]["id"])
        assert steps["deck"] is None
        assert steps["next_lesson"]["id"] == lessons[1]["id"]
        # No wrap-round for a visitor: the last lesson has no next lesson.
        assert lesson_next_steps(None, lessons[-1]["id"])["next_lesson"] is None


def test_sign_up_after_practice_saves_the_lesson(migrated_app, migrated_client):
    """The server half of the flow gate.js runs after a logged-out Practice."""
    lesson = _lessons(migrated_app)[0]
    total = len(lesson["practice"])
    _register(migrated_client)
    response = migrated_client.post(
        f"/api/lessons/{lesson['id']}/complete",
        json={"exercises_correct": total, "exercises_total": total},
    )
    assert response.status_code == 200
    assert response.get_json()["completed"] is True

    html = migrated_client.get(f"/lessons/{lesson['id']}?saved=1").data.decode()
    assert 'id="lesson-saved"' in html
    assert "Saved to your account." in html
    listed = migrated_client.get("/api/levels/a1/lessons").get_json()["lessons"]
    assert [row["id"] for row in listed if row["completed"]] == [lesson["id"]]


def test_carried_completion_uses_the_same_validation(migrated_app, migrated_client):
    lesson = _lessons(migrated_app)[0]
    total = len(lesson["practice"])
    _register(migrated_client)
    for payload in (
        {"exercises_correct": total - 1, "exercises_total": total},
        {"exercises_correct": 1, "exercises_total": 1},
        {"exercises_correct": "9", "exercises_total": "9"},
    ):
        response = migrated_client.post(
            f"/api/lessons/{lesson['id']}/complete", json=payload
        )
        assert response.status_code == 400, payload
    html = migrated_client.get(f"/lessons/{lesson['id']}?saved=1").data.decode()
    # Not completed, so ?saved=1 does not claim anything was saved.
    assert 'id="lesson-saved"' not in html


def test_saved_note_needs_an_account(migrated_app, migrated_client):
    lesson = _lessons(migrated_app)[0]
    html = migrated_client.get(f"/lessons/{lesson['id']}?saved=1").data.decode()
    assert 'id="lesson-saved"' not in html


def _nav_hrefs(html: str) -> dict[str, str | None]:
    nav = re.search(r'<nav class="lesson-nav".*?</nav>', html, re.S)
    assert nav, "lesson page has no course nav"
    block = nav.group(0)

    def href(rel):
        match = re.search(rf'rel="{rel}" href="([^"]+)"', block)
        return match.group(1) if match else None

    all_link = re.search(r'class="lesson-nav__all" href="([^"]+)"', block)
    return {"prev": href("prev"), "next": href("next"), "all": all_link.group(1)}


def test_lessons_link_to_neighbours_in_course_order(migrated_app, migrated_client):
    lessons = _lessons(migrated_app)
    for index, lesson in enumerate(lessons):
        html = migrated_client.get(f"/lessons/{lesson['id']}").data.decode()
        nav = _nav_hrefs(html)
        expected_prev = f"/lessons/{lessons[index - 1]['id']}" if index > 0 else None
        expected_next = (
            f"/lessons/{lessons[index + 1]['id']}" if index + 1 < len(lessons) else None
        )
        assert nav["prev"] == expected_prev, lesson["id"]
        assert nav["next"] == expected_next, lesson["id"]
        # Logged out, "All lessons" goes to the public lesson list.
        assert nav["all"] == "/lessons"


def test_course_nav_ignores_progress_and_links_logged_in_to_level(
    migrated_app, migrated_client
):
    lessons = _lessons(migrated_app)
    _register(migrated_client)
    second = lessons[1]
    response = migrated_client.post(
        f"/api/lessons/{second['id']}/complete",
        json={
            "exercises_correct": len(second["practice"]),
            "exercises_total": len(second["practice"]),
        },
    )
    assert response.status_code == 200
    # Lesson 1's next link is still lesson 2, even though lesson 2 is done.
    nav = _nav_hrefs(migrated_client.get(f"/lessons/{lessons[0]['id']}").data.decode())
    assert nav["next"] == f"/lessons/{second['id']}"
    assert nav["all"] == "/levels/a1"


def test_course_nav_only_on_learn_tab(migrated_app, migrated_client):
    lesson = _lessons(migrated_app)[0]
    html = migrated_client.get(f"/lessons/{lesson['id']}?tab=test").data.decode()
    assert 'class="lesson-nav"' not in html


def test_learn_tab_opens_with_the_lessons_words(migrated_app, migrated_client):
    _lessons(migrated_app)
    with migrated_app.app_context():
        words = get_lesson(None, "noun-gender")["words"]
    assert {"catalan": "la taula", "english": "the table"} in words
    html = migrated_client.get("/lessons/noun-gender").data.decode()
    block = re.search(r'<section class="lesson-words".*?</section>', html, re.S).group(0)
    # The list comes before the lesson's own sections.
    assert html.index(block) < html.index('id="lesson-sections"')
    text = _text(block.encode())
    assert "Words in this lesson" in text
    assert "The test uses these words. Learn them first." in text
    cells = re.findall(r'<td class="examples__ca" lang="ca">([^<]+)</td>', block)
    assert cells == [word["catalan"] for word in words]
    assert "petit / petita" in cells


def test_lesson_without_words_has_no_words_block(migrated_app, migrated_client):
    lessons = _lessons(migrated_app)
    with migrated_app.app_context():
        lesson = db.session.get(Lesson, lessons[1]["id"])
        lesson.words_json = []
        db.session.commit()
    html = migrated_client.get(f"/lessons/{lessons[1]['id']}").data.decode()
    assert 'class="lesson-words"' not in html


def test_old_practice_tab_url_redirects_to_test(migrated_app, migrated_client):
    _lessons(migrated_app)
    response = migrated_client.get("/lessons/noun-gender?tab=practice")
    assert response.status_code == 301
    assert response.headers["Location"] == "/lessons/noun-gender?tab=test"
    # Other query args survive the redirect.
    response = migrated_client.get("/lessons/noun-gender?tab=Practice&saved=1")
    assert response.status_code == 301
    assert response.headers["Location"] == "/lessons/noun-gender?tab=test&saved=1"


def test_test_tab_opens_with_an_intro_card(migrated_app, migrated_client):
    lessons = _lessons(migrated_app)
    lesson = lessons[0]
    html = migrated_client.get(f"/lessons/{lesson['id']}?tab=test").data.decode()
    intro = re.search(r'<div class="stack-lg test-intro" id="test-intro">.*?</button>', html, re.S)
    assert intro, "intro card missing"
    text = _text(intro.group(0).encode())
    assert f"{len(lesson['practice'])} questions" in text
    assert "Get every question right to complete the lesson." in text
    assert "Questions you miss come back at the end." in text
    assert "Start the test" in text
    # The same words list as the Learn tab, so the learner can review it.
    assert "Words in this lesson" in text
    cells = re.findall(r'<td class="examples__ca" lang="ca">([^<]+)</td>', intro.group(0))
    with migrated_app.app_context():
        words = get_lesson(None, lesson["id"])["words"]
    assert cells == [word["catalan"] for word in words]
    # The intro comes before the (hidden until started) progress and questions.
    assert html.index('id="test-intro"') < html.index('id="practice-progress"')
    assert re.search(r'<div class="progress-group" id="practice-progress" hidden>', html)


def test_test_intro_without_words_still_starts(migrated_app, migrated_client):
    lessons = _lessons(migrated_app)
    with migrated_app.app_context():
        lesson = db.session.get(Lesson, lessons[1]["id"])
        lesson.words_json = []
        db.session.commit()
    html = migrated_client.get(f"/lessons/{lessons[1]['id']}?tab=test").data.decode()
    assert 'id="test-intro"' in html
    assert 'class="lesson-words"' not in html
    assert 'id="test-start"' in html


def test_done_panel_has_a_score_block_logged_out(migrated_app, migrated_client):
    lesson = _lessons(migrated_app)[0]
    html = migrated_client.get(f"/lessons/{lesson['id']}?tab=test").data.decode()
    done = re.search(r'<div class="stack" id="practice-done" hidden>(.*?)</div>\s*<p class="field__error"', html, re.S)
    assert done, "done panel missing"
    panel = done.group(1)
    # practice.js fills in the stars and the score; the retry link starts hidden
    # and points back at a fresh test.
    assert 'id="test-score-stars"' in panel
    assert 'id="test-score-text"' in panel
    retry = re.search(r'<a class="test-score__retry" id="test-retry" href="([^"]+)" hidden>([^<]+)</a>', panel)
    assert retry, "retry link missing"
    assert retry.group(1) == f"/lessons/{lesson['id']}?tab=test"
    assert retry.group(2) == "Try again for 3 stars"
