"""Multi-page HTML routes and auth redirects."""

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



def test_index_is_gate_only(client):
    response = client.get("/")
    assert response.status_code == 200
    assert b"Create account" in response.data
    assert b"Sign in" in response.data
    assert b"Your levels" not in response.data
    assert b"screen-lesson" not in response.data
    assert b"js/gate.js" in response.data


def test_levels_requires_login(client):
    response = client.get("/levels")
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/")


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
    assert b"Your levels" in response.data
    assert b"A1" in response.data
    assert b"/levels/a1" in response.data
    assert b"coming soon" in response.data
    assert b">A2<" in response.data or b"A2" in response.data
    assert b">B1<" in response.data or b"B1" in response.data
    assert b"is-disabled" in response.data


def test_level_home_learn_and_vocab(migrated_app, migrated_client):
    with migrated_app.app_context():
        seed_all()
    _register(migrated_client)

    learn = migrated_client.get("/levels/a1")
    assert learn.status_code == 200
    assert b"Noun Gender" in learn.data
    assert b"/lessons/noun-gender" in learn.data

    vocab = migrated_client.get("/levels/a1?tab=vocab")
    assert vocab.status_code == 200
    assert b"Starter" in vocab.data
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
