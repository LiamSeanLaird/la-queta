"""Multi-page HTML routes and auth redirects."""

import re
import struct
from html import unescape

from markupsafe import escape
from sqlalchemy import select

from app.extensions import db
from app.models import Lesson, Level, User
from app.services.seed import seed_all

SIGN_UP_LINK = """href="/signup">Start learning - it's free</a>"""


def _register(client, handle: str = "pageuser"):
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


def test_index_is_a_short_landing_page_that_leads_to_sign_up(
    migrated_app, migrated_client
):
    with migrated_app.app_context():
        seed_all()
    response = migrated_client.get("/")
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert "<title>La Queta - Free Catalan for complete beginners</title>" in html
    assert html.count("<h1") == 1
    assert '<h1 class="heading-1">Free Catalan for complete beginners</h1>' in html
    body = html.split("<body>", 1)[1]
    # The main call to action is sign-up, twice; lesson 1 is the quiet option.
    assert body.count(SIGN_UP_LINK) == 2
    assert 'href="/lessons/noun-gender">or try a lesson first</a>' in body
    assert body.index("Start learning") < body.index("or try a lesson first")
    assert "How it works" in body
    for step in ("Learn a short lesson", "Pass its test", "Review the words each day"):
        assert step in body
    assert 'href="/signin"' in body
    footer = body.split('<footer class="landing-footer">', 1)[1].split("</footer>")[0]
    assert 'href="/lessons">All lessons</a>' in footer
    assert 'href="/faq">FAQ</a>' in footer
    # No lesson list and no FAQ on the landing page.
    assert "/lessons/ser-vs-estar" not in body
    assert "Is it free?" not in body
    assert 'property="og:image"' in html
    assert "og-image.png" in html
    # The forms live on /signup and /signin.
    assert "register-form" not in html
    assert "js/gate.js" not in html


def test_landing_copy_is_short(migrated_app, migrated_client):
    with migrated_app.app_context():
        seed_all()
    html = migrated_client.get("/").get_data(as_text=True)
    main = html.split("<main", 1)[1].split('<footer class="landing-footer">', 1)[0]
    main = re.sub(r"<script.*?</script>", "", main, flags=re.S)
    words = unescape(re.sub(r"<[^>]+>", " ", main)).split()
    assert len(words) < 150, len(words)


def test_landing_shows_the_test_screenshot_in_light_and_dark(
    migrated_app, migrated_client
):
    with migrated_app.app_context():
        seed_all()
    html = migrated_client.get("/").get_data(as_text=True)
    figure = html.split('<figure class="landing-shot">', 1)[1].split("</figure>")[0]
    dark = re.search(
        r'<source srcset="([^"]+)" media="\(prefers-color-scheme: dark\)">', figure
    )
    img = re.search(
        r'<img src="([^"]+)" width="(\d+)" height="(\d+)"[^>]*alt="([^"]+)"', figure
    )
    assert dark and img
    assert "porta" in unescape(img.group(4))
    sizes = set()
    for url in (dark.group(1), img.group(1)):
        response = migrated_client.get(url)
        assert response.status_code == 200
        data = response.data
        response.close()
        assert data[:8] == b"\x89PNG\r\n\x1a\n"
        sizes.add(struct.unpack(">II", data[16:24]))
    # Both images match, at twice the size the page reserves for them.
    assert sizes == {(int(img.group(2)) * 2, int(img.group(3)) * 2)}


def test_lessons_page_lists_every_lesson_by_goal(migrated_app, migrated_client):
    with migrated_app.app_context():
        seed_all()
        lessons = db.session.scalars(
            select(Lesson).where(Lesson.level_id == "a1")
        ).all()
        rows = [(lesson.id, lesson.title, lesson.summary) for lesson in lessons]
    response = migrated_client.get("/lessons")
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert len(rows) == 20
    assert html.count("<h1") == 1
    assert "<h1 class=\"heading-1\">All A1 lessons</h1>" in html
    for lesson_id, title, summary in rows:
        assert f'href="/lessons/{lesson_id}"' in html
        assert escape(title) in html
        assert escape(summary) in html
    # Grouped by goal: every goal label is a heading.
    assert html.count('class="heading-3 goal-section__title"') >= 5
    assert SIGN_UP_LINK in html
    assert "of 3 stars" not in html


def test_lessons_page_logged_in_marks_done_and_hides_sign_up(
    migrated_app, migrated_client
):
    with migrated_app.app_context():
        seed_all()
    _register(migrated_client)
    response = migrated_client.post(
        "/api/lessons/noun-gender/complete",
        json={"exercises_correct": 14, "exercises_total": 14},
    )
    assert response.status_code == 200
    html = migrated_client.get("/lessons").get_data(as_text=True)
    # No first-try score was sent, so the lesson shows as done with 1 star.
    assert html.count('aria-label="Done, 1 of 3 stars"') == 1
    assert 'href="/signup"' not in html


def test_faq_page_shows_every_question(migrated_app, migrated_client):
    with migrated_app.app_context():
        seed_all()
    response = migrated_client.get("/faq")
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert html.count("<h1") == 1
    for question in ("Is it free?", "Do I need an account?", "What comes after A1?"):
        assert question in html
    assert "The course is 20 lessons" in html
    assert SIGN_UP_LINK in html


def test_public_pages_render_before_content_is_seeded(migrated_client):
    for path in ("/lessons", "/faq"):
        assert migrated_client.get(path).status_code == 200, path


def test_index_renders_before_content_is_seeded(migrated_client):
    response = migrated_client.get("/")
    assert response.status_code == 200
    assert "Free Catalan for complete beginners" in response.get_data(as_text=True)


def _gate_blurb(html: str) -> str:
    """Visible text of the gate's blurb paragraph."""
    match = re.search(r'<p[^>]*id="gate-blurb"[^>]*>(.*?)</p>', html, re.S)
    assert match is not None
    return match.group(1).strip()


def test_signup_and_signin_pages_hold_the_gate(migrated_client):
    signup = migrated_client.get("/signup").get_data(as_text=True)
    assert "<title>Create a free account - La Queta</title>" in signup
    assert '<form id="register-form" class="stack">' in signup
    assert '<form id="login-form" class="stack" hidden>' in signup
    assert '<meta name="robots" content="noindex">' in signup
    assert "js/gate.js" in signup
    assert signup.count("<h1") == 1
    assert _gate_blurb(signup) == (
        "An account saves your progress on any device and adds vocab flashcards and a daily review."
    )

    signin = migrated_client.get("/signin").get_data(as_text=True)
    assert "<title>Sign in - La Queta</title>" in signin
    assert '<form id="register-form" class="stack" hidden>' in signin
    assert '<form id="login-form" class="stack">' in signin
    assert '<meta name="robots" content="noindex">' in signin
    assert _gate_blurb(signin) == "Sign in with your email and password."


def test_auth_pages_redirect_when_logged_in(migrated_client):
    _register(migrated_client)
    for path in ("/signup", "/signin"):
        response = migrated_client.get(path)
        assert response.status_code == 302
        assert response.headers["Location"].endswith("/levels")


def test_brand_is_not_a_heading(migrated_client):
    html = migrated_client.get("/signup").get_data(as_text=True)
    assert '<p class="brand__title">' in html
    assert '<h1 class="brand__title">' not in html


def test_levels_requires_login(client):
    response = client.get("/levels")
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/signin")


def test_index_redirects_when_logged_in(migrated_client):
    _register(migrated_client)
    response = migrated_client.get("/")
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/levels")


def test_levels_hub_renders(migrated_app, migrated_client):
    with migrated_app.app_context():
        seed_all()
    _register(migrated_client)
    response = migrated_client.get("/levels")
    assert response.status_code == 200
    assert b"Daily vocab" in response.data
    assert b"Your levels" not in response.data
    assert b"A1" in response.data
    assert b"/levels/a1" in response.data
    # One A1 course: the A2 and B1 placeholders stay in the database but the
    # hub no longer shows "coming soon" tiles for them.
    assert b"<title>La Queta - your A1 course</title>" in response.data
    assert response.data.count(b"<h1") == 1
    assert b"Your A1 course</h1>" in response.data
    assert b"coming soon" not in response.data
    assert b"is-disabled" not in response.data
    assert b"/levels/a2" not in response.data
    assert b"/levels/b1" not in response.data
    assert b"\xc2\xb7 current" not in response.data


def test_levels_hub_works_when_current_level_is_not_open(migrated_app, migrated_client):
    with migrated_app.app_context():
        seed_all()
    _register(migrated_client)
    with migrated_app.app_context():
        user = db.session.scalars(select(User)).one()
        assert db.session.get(Level, "a2") is not None
        user.current_level_id = "a2"
        db.session.commit()
    response = migrated_client.get("/levels")
    assert response.status_code == 200
    assert b"Your A1 course</h1>" in response.data
    assert b"/levels/a1" in response.data
    assert b"/levels/a1/daily" in response.data
    assert b"/levels/a2" not in response.data
    assert migrated_client.get("/levels/a2").headers["Location"].endswith("/levels")


def test_level_home_learn_and_vocab(migrated_app, migrated_client):
    with migrated_app.app_context():
        seed_all()
    _register(migrated_client)

    learn = migrated_client.get("/levels/a1")
    assert learn.status_code == 200
    assert b"<title>La Queta - A1 course</title>" in learn.data
    assert learn.data.count(b"<h1") == 1
    assert b"A1 course</h1>" in learn.data
    assert b"Noun Gender" in learn.data
    assert b"/lessons/noun-gender" in learn.data

    vocab = migrated_client.get("/levels/a1?tab=vocab")
    assert vocab.status_code == 200
    assert b"Greetings &amp; Introductions" in vocab.data
    assert b"/decks/starter" in vocab.data


def test_lesson_page_renders(migrated_app, migrated_client):
    with migrated_app.app_context():
        seed_all()
    _register(migrated_client)
    response = migrated_client.get("/lessons/noun-gender")
    assert response.status_code == 200
    assert b"Noun Gender" in response.data
    assert b">Test</a" in response.data
    assert b"tab=test" in response.data

    practice = migrated_client.get("/lessons/noun-gender?tab=test")
    assert practice.status_code == 200
    assert b"js/practice.js" in practice.data


def test_deck_study_browse_pages(migrated_app, migrated_client):
    with migrated_app.app_context():
        seed_all()
    _register(migrated_client)

    deck = migrated_client.get("/decks/starter")
    assert deck.status_code == 200
    assert b"Study" in deck.data
    assert b"/decks/starter/study" in deck.data
    assert b"progress__bar" in deck.data
    assert b"retired" in deck.data

    study = migrated_client.get("/decks/starter/study")
    assert study.status_code == 200
    assert b"js/study.js" in study.data
    assert b"study-back" in study.data
    assert b"retire-dialog" in study.data
    assert b"study-tip-dialog" in study.data
    assert b"Don\xe2\x80\x99t show again" in study.data

    browse = migrated_client.get("/decks/starter/browse")
    assert browse.status_code == 200
    assert b"Bon dia" in browse.data
