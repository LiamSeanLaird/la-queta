"""Continue action on each level card on /levels."""

from __future__ import annotations

from html.parser import HTMLParser


from app.extensions import db
from app.models import User
from app.services.seed import seed_all


def _register(client, handle: str = "continuer"):
    response = client.post(
        "/api/auth/register",
        json={"handle": handle, "email": f"{handle}@example.com", "password": "password1"},
    )
    assert response.status_code == 201
    return response.get_json()


class _NestedLinkFinder(HTMLParser):
    def __init__(self):
        super().__init__()
        self.depth = 0
        self.nested = 0

    def handle_starttag(self, tag, attrs):
        if tag == "a":
            if self.depth:
                self.nested += 1
            self.depth += 1

    def handle_endtag(self, tag):
        if tag == "a":
            self.depth -= 1


def test_level_card_has_continue_as_main_action(migrated_app, migrated_client):
    with migrated_app.app_context():
        seed_all()
    _register(migrated_client)
    page = migrated_client.get("/levels").get_data(as_text=True)

    continue_btn = (
        '<a class="btn btn--primary btn--block level-tile__continue" '
        'href="/continue?level=a1">Continue: Noun Gender</a>'
    )
    assert continue_btn in page
    assert 'class="btn btn--secondary btn--block daily-cta__btn"' in page
    assert page.index("Continue: Noun Gender") < page.index("Daily vocab")
    assert 'href="/levels/a1"' in page
    # Only the open level gets a Continue action.
    assert page.count("level-tile__continue") == 1


def test_level_card_links_do_not_nest(migrated_app, migrated_client):
    with migrated_app.app_context():
        seed_all()
    _register(migrated_client)
    migrated_client.post("/api/levels/a1/daily/complete", json={"timezone": "UTC"})
    finder = _NestedLinkFinder()
    finder.feed(migrated_client.get("/levels").get_data(as_text=True))
    assert finder.nested == 0
    assert finder.depth == 0


def test_continue_with_level_selects_it_and_redirects(migrated_app, migrated_client):
    with migrated_app.app_context():
        seed_all()
    user = _register(migrated_client)
    response = migrated_client.get("/continue?level=a1")
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/lessons/noun-gender")
    with migrated_app.app_context():
        assert db.session.get(User, user["id"]).current_level_id == "a1"


def test_continue_with_closed_or_unknown_level_goes_to_levels(migrated_app, migrated_client):
    with migrated_app.app_context():
        seed_all()
    _register(migrated_client)
    for level in ("a2", "zz", "../a1"):
        response = migrated_client.get(f"/continue?level={level}")
        assert response.status_code == 302
        assert response.headers["Location"].endswith("/levels")


def test_continue_requires_login(migrated_app, migrated_client):
    with migrated_app.app_context():
        seed_all()
    response = migrated_client.get("/continue?level=a1")
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/")


def test_finished_level_says_done_instead_of_dead_button(
    migrated_app, migrated_client, monkeypatch
):
    import app.routes.pages as pages

    with migrated_app.app_context():
        seed_all()
    _register(migrated_client)
    monkeypatch.setattr(pages, "continue_target", lambda user, level_id=None: None)
    page = migrated_client.get("/levels").get_data(as_text=True)
    assert "level-tile__continue" not in page
    assert "All A1 lessons and vocab done" in page
    assert "Daily vocab" in page
