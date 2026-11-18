"""Crawl basics for search engines: /robots.txt and /sitemap.xml.

Absolute URLs come from PUBLIC_BASE_URL only, never the request host, matching
the canonical rule in base.html. With it unset, robots.txt has no Sitemap line
and /sitemap.xml is a 404, because a sitemap must list absolute URLs.

The sitemap lists only indexable pages (the ones that set canonical_path): the
home page and every lesson in an open level. It has no <lastmod>, because the
server has no honest source for when a lesson last changed.
"""

from xml.sax.saxutils import escape

from flask import Blueprint, Response, abort, current_app, url_for
from sqlalchemy import select

from app.extensions import db
from app.models import Lesson, Level
from app.services.levels import OPEN_LEVEL_IDS

bp = Blueprint("crawl", __name__)

# Logged-in-only routes. Logged out they redirect to /signin, so crawling them
# only wastes crawl budget. /signin, /signup and /style-guide stay crawlable so
# Google can read their noindex meta tag.
DISALLOWED_PREFIXES = ("/api/", "/continue", "/levels", "/decks/")


def _base_url() -> str:
    return (current_app.config.get("PUBLIC_BASE_URL") or "").rstrip("/")


def sitemap_paths() -> list[str]:
    """Paths of every indexable page, home first, then lessons in course order."""
    lesson_ids = db.session.scalars(
        select(Lesson.id)
        .join(Level, Level.id == Lesson.level_id)
        .where(Lesson.level_id.in_(OPEN_LEVEL_IDS))
        .order_by(Level.sort_order, Lesson.sort_order, Lesson.id)
    ).all()
    return [url_for("pages.index")] + [
        url_for("pages.lesson", lesson_id=lesson_id) for lesson_id in lesson_ids
    ]


@bp.get("/robots.txt")
def robots_txt():
    lines = ["User-agent: *", "Allow: /"]
    lines += [f"Disallow: {prefix}" for prefix in DISALLOWED_PREFIXES]
    base = _base_url()
    if base:
        lines += ["", f"Sitemap: {base}{url_for('crawl.sitemap_xml')}"]
    return Response("\n".join(lines) + "\n", mimetype="text/plain")


@bp.get("/sitemap.xml")
def sitemap_xml():
    base = _base_url()
    if not base:
        abort(404)
    entries = "".join(
        f"  <url><loc>{escape(base + path)}</loc></url>\n" for path in sitemap_paths()
    )
    body = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        f"{entries}"
        "</urlset>\n"
    )
    return Response(body, mimetype="application/xml")
