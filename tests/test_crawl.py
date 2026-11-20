"""robots.txt and sitemap.xml: absolute URLs from PUBLIC_BASE_URL, public pages only."""

import xml.etree.ElementTree as ET

from sqlalchemy import select

from app.extensions import db
from app.models import Lesson
from app.services.seed import seed_all

BASE = "https://la-queta.com"
NS = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}


def _seed(app) -> list[str]:
    with app.app_context():
        seed_all()
        return list(db.session.scalars(select(Lesson.id)).all())


def _locs(response) -> list[str]:
    root = ET.fromstring(response.data)
    assert root.tag == "{http://www.sitemaps.org/schemas/sitemap/0.9}urlset"
    return [loc.text for loc in root.findall("sm:url/sm:loc", NS)]


def test_robots_points_to_sitemap_and_blocks_private_routes(
    migrated_app, migrated_client
):
    migrated_app.config["PUBLIC_BASE_URL"] = BASE + "/"
    response = migrated_client.get("/robots.txt", headers={"Host": "www.example.org"})
    assert response.status_code == 200
    assert response.mimetype == "text/plain"
    lines = response.get_data(as_text=True).splitlines()
    assert lines[0] == "User-agent: *"
    assert "Allow: /" in lines
    for prefix in ("/api/", "/continue", "/levels", "/decks/"):
        assert f"Disallow: {prefix}" in lines
    # Absolute, from PUBLIC_BASE_URL (trailing slash trimmed), not the Host header.
    assert f"Sitemap: {BASE}/sitemap.xml" in lines
    # Lessons, the home page and the auth pages stay crawlable.
    disallowed = [
        line.split(": ", 1)[1] for line in lines if line.startswith("Disallow")
    ]
    for path in ("/", "/lessons", "/faq", "/lessons/ser-vs-estar", "/signin", "/signup"):
        assert not any(path.startswith(prefix) for prefix in disallowed), path


def test_robots_has_no_sitemap_without_public_base_url(migrated_client):
    body = migrated_client.get("/robots.txt").get_data(as_text=True)
    assert "Sitemap:" not in body
    assert "Disallow: /api/" in body


def test_sitemap_lists_public_pages_and_every_lesson(migrated_app, migrated_client):
    lesson_ids = _seed(migrated_app)
    assert len(lesson_ids) >= 20
    migrated_app.config["PUBLIC_BASE_URL"] = BASE
    response = migrated_client.get("/sitemap.xml", headers={"Host": "www.example.org"})
    assert response.status_code == 200
    assert response.mimetype == "application/xml"
    locs = _locs(response)
    assert locs[:3] == [f"{BASE}/", f"{BASE}/lessons", f"{BASE}/faq"]
    assert sorted(locs[3:]) == sorted(f"{BASE}/lessons/{i}" for i in lesson_ids)
    assert len(set(locs)) == len(locs)
    # No <lastmod>: the server has no honest source for it.
    assert b"lastmod" not in response.data


def test_sitemap_urls_are_public_and_match_canonicals(migrated_app, migrated_client):
    _seed(migrated_app)
    migrated_app.config["PUBLIC_BASE_URL"] = BASE
    for loc in _locs(migrated_client.get("/sitemap.xml")):
        assert loc.startswith(BASE + "/")
        path = loc[len(BASE) :]
        assert not path.startswith(("/api/", "/levels", "/decks/", "/continue"))
        # A fresh, logged-out client sees each page and its canonical is the loc.
        page = migrated_app.test_client().get(path)
        assert page.status_code == 200, path
        assert f'<link rel="canonical" href="{loc}">' in page.get_data(as_text=True)
        assert 'name="robots" content="noindex"' not in page.get_data(as_text=True)


def test_sitemap_is_404_without_public_base_url(migrated_app, migrated_client):
    _seed(migrated_app)
    assert migrated_client.get("/sitemap.xml").status_code == 404


def test_sitemap_with_no_content_lists_only_static_pages(
    migrated_app, migrated_client
):
    migrated_app.config["PUBLIC_BASE_URL"] = BASE
    assert _locs(migrated_client.get("/sitemap.xml")) == [
        f"{BASE}/",
        f"{BASE}/lessons",
        f"{BASE}/faq",
    ]
