from flask import Blueprint, redirect, render_template, request, url_for
from sqlalchemy import select

from app.extensions import db
from app.models import Deck, Level
from app.services.auth import current_user
from app.services.errors import ServiceError
from app.services.can_dos import list_can_dos_for_level
from app.services.lessons import get_lesson, list_lessons_for_level
from app.services.levels import list_levels_for_user, select_level, level_is_open
from app.services.progress import continue_target, level_completeness_pct
from app.services.vocab import list_cards_for_deck, list_decks_for_level

bp = Blueprint("pages", __name__)


def _login_required():
    user = current_user()
    if user is None:
        return None, redirect(url_for("pages.index"))
    return user, None


def _continue_href(target: dict) -> str:
    if target["kind"] == "lesson":
        return url_for("pages.lesson", lesson_id=target["lesson_id"])
    return url_for("pages.study", slug=target["slug"])


@bp.get("/")
def index():
    if current_user() is not None:
        return redirect(url_for("pages.levels"))
    return render_template("index.html")


@bp.get("/continue")
def continue_learning():
    user, bounced = _login_required()
    if bounced:
        return bounced
    target = continue_target(user)
    if target is None:
        return redirect(url_for("pages.levels"))
    select_level(user, target["level_id"])
    return redirect(_continue_href(target))


@bp.get("/levels")
def levels():
    user, bounced = _login_required()
    if bounced:
        return bounced
    target = continue_target(user)
    return render_template(
        "levels.html",
        user=user,
        levels=list_levels_for_user(user),
        continue_target=target,
        continue_href=_continue_href(target) if target else None,
    )


@bp.get("/levels/<level_id>")
def level_home(level_id: str):
    user, bounced = _login_required()
    if bounced:
        return bounced
    try:
        user = select_level(user, level_id)
    except ServiceError:
        return redirect(url_for("pages.levels"))

    level = db.session.get(Level, level_id)
    if level is None:
        return redirect(url_for("pages.levels"))

    tab = request.args.get("tab", "learn")
    if tab not in {"learn", "vocab"}:
        tab = "learn"

    lessons = list_lessons_for_level(user, level_id) if tab == "learn" else []
    decks = list_decks_for_level(user, level_id) if tab == "vocab" else []
    can_dos = list_can_dos_for_level(user, level_id) if tab == "learn" else []
    target = continue_target(user, level_id=level_id)
    return render_template(
        "level.html",
        user=user,
        level=level,
        tab=tab,
        lessons=lessons,
        decks=decks,
        can_dos=can_dos,
        complete_pct=level_completeness_pct(user.id, level_id),
        continue_target=target,
        continue_href=_continue_href(target) if target else None,
        brand_href=url_for("pages.levels"),
    )


@bp.get("/lessons/<lesson_id>")
def lesson(lesson_id: str):
    user, bounced = _login_required()
    if bounced:
        return bounced
    try:
        lesson_data = get_lesson(user, lesson_id)
    except ServiceError:
        return redirect(url_for("pages.levels"))

    tab = (request.args.get("tab") or "learn").strip().lower()
    if tab not in {"learn", "practice"}:
        tab = "learn"

    next_target = None
    next_href = None
    if lesson_data["completed"]:
        next_target = continue_target(user, level_id=lesson_data["level_id"])
        if next_target is not None:
            next_href = _continue_href(next_target)

    return render_template(
        "lesson.html",
        user=user,
        lesson=lesson_data,
        tab=tab,
        next_target=next_target,
        next_href=next_href,
        brand_href=url_for("pages.levels"),
    )


def _deck_context(user, slug: str) -> dict:
    deck = db.session.scalar(select(Deck).where(Deck.slug == slug))
    if deck is None:
        raise ServiceError("Deck not found", 404)
    decks = list_decks_for_level(user, deck.level_id)
    stats = next((row for row in decks if row["slug"] == slug), None)
    if stats is None:
        raise ServiceError("Deck not found", 404)
    return {
        "slug": deck.slug,
        "title": deck.title,
        "level_id": deck.level_id,
        "total": stats["total"],
        "retired": stats["retired"],
        "remaining": stats["remaining"],
    }


@bp.get("/decks/<slug>")
def deck(slug: str):
    user, bounced = _login_required()
    if bounced:
        return bounced
    try:
        deck_data = _deck_context(user, slug)
    except ServiceError:
        return redirect(url_for("pages.levels"))
    return render_template(
        "deck.html",
        user=user,
        deck=deck_data,
        brand_href=url_for("pages.levels"),
    )


@bp.get("/decks/<slug>/study")
def study(slug: str):
    user, bounced = _login_required()
    if bounced:
        return bounced
    try:
        deck_data = _deck_context(user, slug)
    except ServiceError:
        return redirect(url_for("pages.levels"))
    return render_template(
        "study.html",
        user=user,
        study_title=f"Study {deck_data['title']}",
        session_url=url_for("api_vocab.deck_session", slug=slug),
        exit_url=url_for("pages.deck", slug=slug),
        back_label="← Deck",
        done_message="Deck complete for now — all cards retired or none left.",
        brand_href=url_for("pages.levels"),
    )


@bp.get("/levels/<level_id>/daily")
def daily(level_id: str):
    user, bounced = _login_required()
    if bounced:
        return bounced
    if not level_is_open(level_id):
        return redirect(url_for("pages.levels"))
    level = db.session.get(Level, level_id)
    if level is None:
        return redirect(url_for("pages.levels"))
    return render_template(
        "study.html",
        user=user,
        study_title=f"Daily vocab · {level.code}",
        session_url=url_for("api_vocab.level_daily", level_id=level_id),
        exit_url=url_for("pages.level_home", level_id=level_id, tab="vocab"),
        back_label="← Vocab",
        done_message="Daily session complete.",
        brand_href=url_for("pages.levels"),
    )


@bp.get("/decks/<slug>/browse")
def browse(slug: str):
    user, bounced = _login_required()
    if bounced:
        return bounced
    try:
        deck_data = _deck_context(user, slug)
        cards = list_cards_for_deck(user, slug)
    except ServiceError:
        return redirect(url_for("pages.levels"))
    return render_template(
        "browse.html",
        user=user,
        deck=deck_data,
        cards=cards,
        brand_href=url_for("pages.levels"),
    )


@bp.get("/style-guide")
def style_guide():
    return render_template("style_guide.html")
