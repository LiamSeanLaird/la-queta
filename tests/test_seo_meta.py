"""On-page SEO: unique lesson titles and descriptions, canonical URLs, noindex."""

import re
from html import unescape

from sqlalchemy import select

from app.extensions import db
from app.models import Lesson
from app.routes.pages import lesson_page_description, lesson_page_title
from app.services.seed import seed_all

BASE = "https://la-queta.com"


def _seed_lessons(app):
    with app.app_context():
        seed_all()
        rows = db.session.scalars(
            select(Lesson).order_by(Lesson.sort_order, Lesson.id)
        ).all()
        return [(row.id, row.title, row.summary) for row in rows]


def _head(html: str) -> str:
    return html.split("</head>", 1)[0]


def _title(html: str) -> str:
    return unescape(re.search(r"<title>(.*?)</title>", html, re.S).group(1)).strip()


def _description(html: str) -> str:
    match = re.search(r'<meta name="description" content="(.*?)">', html, re.S)
    return unescape(match.group(1)).strip()


def _canonicals(html: str) -> list[str]:
    return re.findall(r'<link rel="canonical" href="(.*?)">', _head(html))


def _register(client):
    response = client.post(
        "/api/auth/register",
        json={
            "handle": "Seo",
            "email": "seo@example.com",
            "password": "password123",
        },
    )
    assert response.status_code == 201


def test_lesson_page_title_and_description_helpers():
    assert (
        lesson_page_title("Ser vs Estar")
        == "Ser vs estar in Catalan - free A1 lesson | La Queta"
    )
    assert lesson_page_title("Food & Café").startswith("Food & café in Catalan")
    assert lesson_page_description("Say hello.") == (
        "Say hello. A free A1 Catalan lesson with practice, no sign-up needed."
    )


def test_every_lesson_has_unique_title_description_and_canonical(
    migrated_app, migrated_client
):
    migrated_app.config["PUBLIC_BASE_URL"] = BASE + "/"
    lessons = _seed_lessons(migrated_app)
    titles, descriptions = set(), set()
    for lesson_id, title, summary in lessons:
        html = migrated_client.get(f"/lessons/{lesson_id}?tab=practice").get_data(
            as_text=True
        )
        page_title = _title(html)
        assert page_title == lesson_page_title(title)
        assert "Catalan" in page_title
        description = _description(html)
        assert description.startswith(summary.strip())
        titles.add(page_title)
        descriptions.add(description)
        # Canonical: absolute, from PUBLIC_BASE_URL, no query string.
        assert _canonicals(html) == [f"{BASE}/lessons/{lesson_id}"]
        assert f'<meta property="og:url" content="{BASE}/lessons/{lesson_id}">' in html
        assert "noindex" not in _head(html)
        # The on-page heading keeps the lesson's own title.
        assert html.count("<h1") == 1
        assert f'<h1 class="heading-1">{title}</h1>' in unescape(html)
    assert len(titles) == len(lessons)
    assert len(descriptions) == len(lessons)


def test_canonical_ignores_request_host(migrated_app, migrated_client):
    migrated_app.config["PUBLIC_BASE_URL"] = BASE
    lesson_id = _seed_lessons(migrated_app)[0][0]
    html = migrated_client.get(
        f"/lessons/{lesson_id}", headers={"Host": "www.example.org"}
    ).get_data(as_text=True)
    assert _canonicals(html) == [f"{BASE}/lessons/{lesson_id}"]


def test_home_canonical(migrated_app, migrated_client):
    migrated_app.config["PUBLIC_BASE_URL"] = BASE
    _seed_lessons(migrated_app)
    html = migrated_client.get("/?ref=x").get_data(as_text=True)
    assert _canonicals(html) == [f"{BASE}/"]
    assert "noindex" not in _head(html)


def test_no_canonical_without_public_base_url(migrated_app, migrated_client):
    lesson_id = _seed_lessons(migrated_app)[0][0]
    assert migrated_app.config["PUBLIC_BASE_URL"] == ""
    for path in ("/", f"/lessons/{lesson_id}"):
        html = migrated_client.get(path).get_data(as_text=True)
        assert _canonicals(html) == []
        assert "noindex" not in _head(html)


def test_private_and_auth_pages_are_noindex(migrated_app, migrated_client):
    migrated_app.config["PUBLIC_BASE_URL"] = BASE
    _seed_lessons(migrated_app)
    for path in ("/signup", "/signin"):
        html = migrated_client.get(path).get_data(as_text=True)
        assert '<meta name="robots" content="noindex">' in _head(html)
        assert _canonicals(html) == []

    _register(migrated_client)
    with migrated_app.app_context():
        deck_slug = db.session.execute(
            db.text("SELECT slug FROM decks ORDER BY sort_order LIMIT 1")
        ).scalar_one()
    for path in (
        "/levels",
        "/levels/a1",
        "/levels/a1/daily",
        f"/decks/{deck_slug}",
        f"/decks/{deck_slug}/study",
        f"/decks/{deck_slug}/browse",
    ):
        response = migrated_client.get(path)
        assert response.status_code == 200, path
        html = response.get_data(as_text=True)
        assert '<meta name="robots" content="noindex">' in _head(html), path
        assert _canonicals(html) == [], path


def test_logged_in_lesson_keeps_canonical(migrated_app, migrated_client):
    migrated_app.config["PUBLIC_BASE_URL"] = BASE
    lesson_id = _seed_lessons(migrated_app)[0][0]
    _register(migrated_client)
    html = migrated_client.get(f"/lessons/{lesson_id}").get_data(as_text=True)
    assert _canonicals(html) == [f"{BASE}/lessons/{lesson_id}"]
    assert "noindex" not in _head(html)


def test_every_page_has_one_h1(migrated_app, migrated_client):
    lesson_id = _seed_lessons(migrated_app)[0][0]
    public = ("/", "/signup", "/signin", f"/lessons/{lesson_id}", "/style-guide")
    for path in public:
        html = migrated_client.get(path).get_data(as_text=True)
        assert html.count("<h1") == 1, path

    _register(migrated_client)
    with migrated_app.app_context():
        deck_slug, deck_title = db.session.execute(
            db.text("SELECT slug, title FROM decks ORDER BY sort_order LIMIT 1")
        ).one()
    expected = {
        "/levels": "Your A1 course",
        "/levels/a1": "A1 course",
        "/levels/a1/daily": "Daily vocab · A1",
        f"/lessons/{lesson_id}": None,
        f"/decks/{deck_slug}": deck_title,
        f"/decks/{deck_slug}/study": f"Study {deck_title}",
        f"/decks/{deck_slug}/browse": deck_title,
    }
    for path, heading in expected.items():
        response = migrated_client.get(path)
        assert response.status_code == 200, path
        html = unescape(response.get_data(as_text=True))
        assert html.count("<h1") == 1, path
        if heading:
            assert re.search(rf"<h1[^>]*>{re.escape(heading)}</h1>", html), path
