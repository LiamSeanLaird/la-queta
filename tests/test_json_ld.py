"""JSON-LD structured data: Course on /, FAQPage on /faq, LearningResource on lessons."""

import json
import re

from sqlalchemy import select

from app.extensions import db
from app.models import Lesson
from app.services.seed import seed_all

BASE = "https://la-queta.com"


def _json_ld(html: str) -> list[dict]:
    head = html.split("</head>", 1)[0]
    blocks = re.findall(
        r'<script type="application/ld\+json">(.*?)</script>', head, re.S
    )
    return [json.loads(block) for block in blocks]


def _by_type(items: list[dict], kind: str) -> dict:
    matches = [item for item in items if item["@type"] == kind]
    assert len(matches) == 1, f"expected one {kind}, got {len(matches)}"
    return matches[0]


def _seed(app) -> list[tuple]:
    with app.app_context():
        seed_all()
        rows = db.session.scalars(
            select(Lesson).order_by(Lesson.sort_order, Lesson.id)
        ).all()
        return [(row.id, row.title, row.summary, row.sort_order) for row in rows]


def test_home_has_course_json_ld(migrated_app, migrated_client):
    migrated_app.config["PUBLIC_BASE_URL"] = BASE
    lessons = _seed(migrated_app)
    html = migrated_client.get("/").get_data(as_text=True)
    items = _json_ld(html)
    assert len(items) == 1
    assert items[0]["@context"] == "https://schema.org"

    course = _by_type(items, "Course")
    assert course["name"]
    assert str(len(lessons)) in course["description"]
    assert course["provider"] == {
        "@type": "Organization",
        "name": "La Queta",
        "url": BASE + "/",
    }
    assert course["url"] == BASE + "/"
    assert course["inLanguage"] == "en"
    assert course["teaches"] == "Catalan"
    assert course["educationalLevel"] == "A1"
    assert course["isAccessibleForFree"] is True
    assert course["offers"]["price"] == 0
    assert course["hasCourseInstance"]["courseMode"] == "Online"


def test_faq_page_has_faq_json_ld(migrated_app, migrated_client):
    migrated_app.config["PUBLIC_BASE_URL"] = BASE
    _seed(migrated_app)
    html = migrated_client.get("/faq").get_data(as_text=True)
    items = _json_ld(html)
    assert len(items) == 1
    assert items[0]["@context"] == "https://schema.org"
    faq = _by_type(items, "FAQPage")
    questions = faq["mainEntity"]
    assert len(questions) == 5
    for question in questions:
        assert question["@type"] == "Question"
        assert question["name"].endswith("?")
        assert question["acceptedAnswer"]["@type"] == "Answer"
        assert question["acceptedAnswer"]["text"]
        # Google requires the FAQ markup to match text visible on the page.
        assert question["name"] in html.split("</head>", 1)[1]
    names = [question["name"] for question in questions]
    assert "Is it free?" in names
    assert "Do I need an account?" in names


def test_lesson_pages_have_learning_resource_json_ld(migrated_app, migrated_client):
    migrated_app.config["PUBLIC_BASE_URL"] = BASE
    lessons = _seed(migrated_app)
    assert lessons
    for lesson_id, title, summary, sort_order in lessons:
        html = migrated_client.get(f"/lessons/{lesson_id}?tab=test").get_data(
            as_text=True
        )
        items = _json_ld(html)
        assert len(items) == 1
        resource = items[0]
        assert resource["@context"] == "https://schema.org"
        assert resource["@type"] == "LearningResource"
        assert resource["name"] == title
        assert resource["description"].startswith(summary.strip())
        assert resource["url"] == f"{BASE}/lessons/{lesson_id}"
        assert resource["learningResourceType"] == "Lesson"
        assert resource["inLanguage"] == "en"
        assert resource["educationalLevel"] == "A1"
        assert resource["isAccessibleForFree"] is True
        assert resource["position"] == sort_order
        assert resource["isPartOf"]["@type"] == "Course"
        assert resource["isPartOf"]["url"] == BASE + "/"


def test_json_ld_has_no_urls_without_public_base_url(migrated_client, migrated_app):
    lessons = _seed(migrated_app)
    for path in ("/", "/faq", f"/lessons/{lessons[0][0]}"):
        html = migrated_client.get(path, headers={"Host": "www.example.com"})
        text = html.get_data(as_text=True)
        assert "example.com" not in "".join(json.dumps(item) for item in _json_ld(text))
        for item in _json_ld(text):
            assert "url" not in item


def test_json_ld_escapes_html(migrated_app, migrated_client):
    migrated_app.config["PUBLIC_BASE_URL"] = BASE
    lessons = _seed(migrated_app)
    with migrated_app.app_context():
        lesson = db.session.get(Lesson, lessons[0][0])
        lesson.summary = "Bad </script><script>alert(1)</script> & co."
        db.session.commit()
    html = migrated_client.get(f"/lessons/{lessons[0][0]}").get_data(as_text=True)
    head = html.split("</head>", 1)[0]
    assert "alert(1)</script>" not in head
    assert _json_ld(html)[0]["teaches"].startswith("Bad </script>")


def test_noindex_pages_have_no_json_ld(migrated_client, migrated_app):
    _seed(migrated_app)
    for path in ("/signin", "/signup"):
        html = migrated_client.get(path).get_data(as_text=True)
        assert _json_ld(html) == []
