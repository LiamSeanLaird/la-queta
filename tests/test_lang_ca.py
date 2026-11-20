"""Catalan text is marked lang="ca" so screen readers and search engines can tell it apart."""

import json
import re
from html import unescape
from pathlib import Path

from app.services.seed import seed_all

ROOT = Path(__file__).resolve().parent.parent


def test_html_stays_english(migrated_client):
    html = migrated_client.get("/signin").get_data(as_text=True)
    assert '<html lang="en">' in html


def test_brand_tagline_is_catalan(migrated_client):
    html = migrated_client.get("/signin").get_data(as_text=True)
    assert '<p class="brand__tagline" lang="ca">aprèn català</p>' in html


def test_every_lesson_example_is_marked_catalan(migrated_app, migrated_client):
    with migrated_app.app_context():
        seed_all()
    for path in sorted((ROOT / "content" / "lessons").glob("*.json")):
        lesson = json.loads(path.read_text())
        # The "Words in this lesson" list comes first, then the examples.
        examples = [word["catalan"] for word in lesson.get("words", [])] + [
            item["catalan"]
            for section in lesson["sections"]
            if section["type"] == "examples"
            for item in section.get("items", [])
        ]
        if not examples:
            continue
        html = migrated_client.get(f"/lessons/{lesson['id']}").get_data(as_text=True)
        cells = [
            unescape(cell)
            for cell in re.findall(
                r'<td class="examples__ca" lang="ca">(.*?)</td>', html
            )
        ]
        assert cells == examples, lesson["id"]
        assert 'class="examples__ca">' not in html, lesson["id"]
        assert '<th lang="ca">Català</th>' in html, lesson["id"]


def test_browse_plural_is_marked_catalan(migrated_app, migrated_client):
    with migrated_app.app_context():
        seed_all()
    migrated_client.post(
        "/api/auth/register",
        json={"handle": "Lang", "email": "lang@example.com", "password": "password123"},
    )
    html = migrated_client.get("/decks/family/browse").get_data(as_text=True)
    plurals = re.findall(
        r'<span class="gram-pill gram-pill--pl">pl: (.*?)</span>', html
    )
    assert plurals
    assert all(p.startswith('<span lang="ca">') for p in plurals)

