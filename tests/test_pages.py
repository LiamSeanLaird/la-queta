"""Multi-page HTML routes and auth redirects."""

from markupsafe import escape
from sqlalchemy import select

from app.extensions import db
from app.models import Level, User
from app.services.seed import seed_all


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


def test_index_is_landing_page(migrated_app, migrated_client):
    with migrated_app.app_context():
        seed_all()
    response = migrated_client.get("/")
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert "<title>La Queta - Free Catalan for complete beginners</title>" in html
    assert html.count("<h1") == 1
    assert '<h1 class="heading-1">Free Catalan for complete beginners</h1>' in html
    assert 'href="/lessons/noun-gender">Start lesson 1</a>' in html
    assert 'href="/signin"' in html
    assert (
        "What you&#39;ll be able to do" in html or "What you'll be able to do" in html
    )
    assert "Is it free?" in html
    assert "Do I need an account?" in html
    assert "What comes after A1?" in html
    assert 'property="og:image"' in html
    assert "og-image.png" in html
    # The forms live on /signup and /signin now.
    assert "register-form" not in html
    assert "js/gate.js" not in html


def test_index_lists_every_lesson_with_summary(migrated_app, migrated_client):
    from sqlalchemy import select

    from app.extensions import db
    from app.models import Lesson

    with migrated_app.app_context():
        seed_all()
        lessons = db.session.scalars(
            select(Lesson).where(Lesson.level_id == "a1")
        ).all()
        rows = [(lesson.id, lesson.title, lesson.summary) for lesson in lessons]
    html = migrated_client.get("/").get_data(as_text=True)
    assert len(rows) == 20
    assert f"The {len(rows)} lessons" in html
    for lesson_id, title, summary in rows:
        assert f'href="/lessons/{lesson_id}"' in html
        assert escape(title) in html
        assert escape(summary) in html


def test_index_renders_before_content_is_seeded(migrated_client):
    response = migrated_client.get("/")
    assert response.status_code == 200
    assert "Free Catalan for complete beginners" in response.get_data(as_text=True)


def test_signup_and_signin_pages_hold_the_gate(migrated_client):
    signup = migrated_client.get("/signup").get_data(as_text=True)
    assert "<title>Create a free account - La Queta</title>" in signup
    assert '<form id="register-form" class="stack">' in signup
    assert '<form id="login-form" class="stack" hidden>' in signup
    assert '<meta name="robots" content="noindex">' in signup
    assert "js/gate.js" in signup
    assert signup.count("<h1") == 1

    signin = migrated_client.get("/signin").get_data(as_text=True)
    assert "<title>Sign in - La Queta</title>" in signin
    assert '<form id="register-form" class="stack" hidden>' in signin
    assert '<form id="login-form" class="stack">' in signin
    assert '<meta name="robots" content="noindex">' in signin


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
    assert b"Practice" in response.data
    assert b"tab=practice" in response.data

    practice = migrated_client.get("/lessons/noun-gender?tab=practice")
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
