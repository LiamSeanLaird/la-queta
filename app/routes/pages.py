from urllib.parse import urlencode

from flask import (
    Blueprint,
    abort,
    current_app,
    redirect,
    render_template,
    request,
    url_for,
)
from sqlalchemy import select

from app.extensions import db
from app.models import Deck, Level
from app.seo import course_json_ld, faq_json_ld, site_faq, lesson_json_ld
from app.services.auth import current_user
from app.services.errors import ServiceError
from app.services.daily import daily_status
from app.services.can_dos import (
    can_dos_progress,
    learn_groups_for_level,
    vocab_groups_for_level,
)
from app.services.lessons import get_lesson, lesson_neighbours, list_lessons_for_level
from app.services.levels import list_levels_for_user, select_level, level_is_open
from app.services.progress import (
    continue_target,
    deck_lessons,
    deck_next_lesson,
    lesson_next_steps,
    completeness_pct,
    level_progress_counts,
    next_incomplete_lesson,
    progress_summary,
)
from app.services.vocab import list_cards_for_deck, list_decks_for_level

bp = Blueprint("pages", __name__)


def _login_required():
    user = current_user()
    if user is None:
        return None, redirect(url_for("pages.signin"))
    return user, None


def _continue_href(target: dict) -> str:
    if target["kind"] == "lesson":
        return url_for("pages.lesson", lesson_id=target["lesson_id"])
    return url_for("pages.study", slug=target["slug"])


COURSE_LEVEL_ID = "a1"


def _course_overview(user=None) -> dict:
    """The A1 course at a glance, shared by /, /lessons and /faq."""
    try:
        lessons = list_lessons_for_level(user, COURSE_LEVEL_ID)
        learn_groups = learn_groups_for_level(user, COURSE_LEVEL_ID)
    except ServiceError:  # content not seeded yet
        lessons, learn_groups = [], []
    level = db.session.get(Level, COURSE_LEVEL_ID)
    return {
        "lessons": lessons,
        "learn_groups": learn_groups,
        "level_code": level.code if level else COURSE_LEVEL_ID.upper(),
    }


@bp.get("/")
def index():
    """Public landing page: a short pitch that leads to sign-up."""
    if current_user() is not None:
        return redirect(url_for("pages.levels"))
    course = _course_overview()
    lessons = course["lessons"]
    description = (
        "A short, free Catalan course that takes complete beginners from zero to "
        f"{course['level_code']}: {len(lessons)} lessons with tests, plus vocab flashcards."
    )
    base_url = current_app.config.get("PUBLIC_BASE_URL", "")
    return render_template(
        "index.html",
        first_lesson=lessons[0] if lessons else None,
        page_description=description,
        json_ld=[course_json_ld(base_url, description, course["level_code"])],
    )


@bp.get("/lessons")
def lessons_index():
    """Public list of every A1 lesson, grouped by goal. Logged in it still shows."""
    user = current_user()
    course = _course_overview(user)
    lesson_count = len(course["lessons"])
    return render_template(
        "lessons.html",
        user=user,
        lesson_count=lesson_count,
        learn_groups=course["learn_groups"],
        level_code=course["level_code"],
        page_description=(
            f"All {lesson_count} lessons of a free {course['level_code']} Catalan "
            "course for complete beginners, grouped by goal. Each has a short test."
        ),
        brand_href=url_for("pages.levels") if user else url_for("pages.index"),
    )


@bp.get("/faq")
def faq():
    """Public FAQ; its FAQPage JSON-LD is built from the same entries."""
    user = current_user()
    course = _course_overview(user)
    entries = site_faq(len(course["lessons"]))
    return render_template(
        "faq.html",
        user=user,
        faq=entries,
        first_lesson=course["lessons"][0] if course["lessons"] else None,
        page_description=(
            "Questions about La Queta, the free Catalan course for complete "
            "beginners: cost, accounts, which Catalan it teaches and what comes next."
        ),
        json_ld=[faq_json_ld(entries)],
        brand_href=url_for("pages.levels") if user else url_for("pages.index"),
    )


def _auth_page(mode: str):
    if current_user() is not None:
        return redirect(url_for("pages.levels"))
    return render_template("auth.html", mode=mode, brand_href=url_for("pages.index"))


@bp.get("/signup")
def signup():
    return _auth_page("signup")


@bp.get("/signin")
def signin():
    return _auth_page("signin")


@bp.get("/continue")
def continue_learning():
    user, bounced = _login_required()
    if bounced:
        return bounced
    level_id = request.args.get("level") or None
    if level_id is not None and not level_is_open(level_id):
        return redirect(url_for("pages.levels"))
    target = continue_target(user, level_id)
    if target is None:
        return redirect(url_for("pages.levels"))
    select_level(user, target["level_id"])
    return redirect(_continue_href(target))


@bp.get("/levels")
def levels():
    user, bounced = _login_required()
    if bounced:
        return bounced
    # The hub reads as one A1 course: levels without content yet (A2, B1) stay
    # in the database but are not shown. A learner whose current_level_id is
    # one of those still gets the open levels here.
    levels_data = [row for row in list_levels_for_user(user) if row["available"]]
    for row in levels_data:
        progress = can_dos_progress(user, row["id"])
        row["can_dos"] = progress["items"]
        row["goals_done"] = progress["done"]
        row["goals_total"] = progress["total"]
        row["next_goal"] = progress["next"]
        row["continue"] = continue_target(user, row["id"])
    daily_level_id = (
        user.current_level_id if level_is_open(user.current_level_id or "") else None
    )
    if daily_level_id is None:
        daily_level_id = levels_data[0]["id"] if levels_data else None
    daily_href = (
        url_for("pages.daily", level_id=daily_level_id) if daily_level_id else None
    )
    return render_template(
        "levels.html",
        user=user,
        levels=levels_data,
        daily_href=daily_href,
        daily_level_id=daily_level_id,
        daily=daily_status(user) if daily_href else None,
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
    learn_groups = learn_groups_for_level(user, level_id) if tab == "learn" else []
    decks = list_decks_for_level(user, level_id) if tab == "vocab" else []
    vocab_groups = vocab_groups_for_level(user, level_id) if tab == "vocab" else []
    goals = can_dos_progress(user, level_id)
    counts = level_progress_counts(user.id, level_id)
    return render_template(
        "level.html",
        user=user,
        level=level,
        tab=tab,
        lessons=lessons,
        learn_groups=learn_groups,
        decks=decks,
        vocab_groups=vocab_groups,
        can_dos=goals["items"],
        goals_done=goals["done"],
        goals_total=goals["total"],
        goals_pct=goals["pct"],
        complete_pct=completeness_pct(counts),
        progress_summary=progress_summary(counts),
        brand_href=url_for("pages.levels"),
    )


def lesson_page_title(title: str) -> str:
    """Search-friendly <title> for a lesson, e.g. 'Ser vs estar in Catalan - ...'.

    The on-page h1 keeps the lesson's own title; only the <title> says 'Catalan',
    because that is how people search ('Catalan noun gender').
    """
    phrase = title[:1] + title[1:].lower()
    return f"{phrase} in Catalan - free A1 lesson | La Queta"


def lesson_page_description(summary: str) -> str:
    return (
        f"{summary.strip()} A free A1 Catalan lesson with a short test, no sign-up needed."
    )


@bp.get("/lessons/<lesson_id>")
def lesson(lesson_id: str):
    # Public: a logged-out visitor (user=None) can read any lesson and take its test.
    # Only saving the completion (POST /api/lessons/<id>/complete) needs an account.
    user = current_user()
    try:
        lesson_data = get_lesson(user, lesson_id)
    except ServiceError:
        if user:
            return redirect(url_for("pages.levels"))
        # A real 404, not a redirect home: crawlers treat that as a soft 404.
        abort(404)

    tab = (request.args.get("tab") or "learn").strip().lower()
    if tab == "practice":
        # The Test tab used to be called Practice, and ?tab=practice URLs are
        # public and indexed: send them to the new name, keeping other args.
        args = request.args.copy()
        args["tab"] = "test"
        query = urlencode(list(args.items(multi=True)))
        return redirect(f"{url_for('pages.lesson', lesson_id=lesson_id)}?{query}", 301)
    if tab not in {"learn", "test"}:
        tab = "learn"

    next_steps = lesson_next_steps(user, lesson_data["id"])
    neighbours = lesson_neighbours(lesson_data["id"])
    level = db.session.get(Level, lesson_data["level_id"])
    level_code = level.code if level else lesson_data["level_id"].upper()
    page_description = lesson_page_description(lesson_data["summary"])

    return render_template(
        "lesson.html",
        user=user,
        lesson=lesson_data,
        page_title=lesson_page_title(lesson_data["title"]),
        page_description=page_description,
        json_ld=[
            lesson_json_ld(
                current_app.config.get("PUBLIC_BASE_URL", ""),
                lesson_data,
                page_description,
                level_code,
                url_for("pages.lesson", lesson_id=lesson_data["id"]),
            )
        ],
        tab=tab,
        # gate.js lands here with ?saved=1 after saving a lesson the visitor
        # finished before signing up.
        just_saved=bool(user)
        and lesson_data["completed"]
        and request.args.get("saved") == "1",
        next_deck=next_steps["deck"],
        next_lesson=next_steps["next_lesson"],
        finishes_level=next_steps["finishes_level"],
        just_finished_level=bool(user)
        and lesson_data["completed"]
        and next_steps["finishes_level"]
        and request.args.get("saved") == "1"
        and request.args.get("finished") == "1",
        level_code=level_code,
        previous_in_course=neighbours["previous"],
        next_in_course=neighbours["next"],
        # Logged out, the public course page is the lesson list on /lessons.
        course_href=(
            url_for("pages.level_home", level_id=lesson_data["level_id"])
            if user
            else url_for("pages.lessons_index")
        ),
        brand_href=url_for("pages.levels") if user else url_for("pages.index"),
        back_href=(
            url_for("pages.level_home", level_id=lesson_data["level_id"])
            if user
            else url_for("pages.index")
        ),
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
        lessons=deck_lessons(user, slug, deck_data["level_id"]),
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
        back_label="Back to deck",
        empty_message="Every card in this deck is retired. Unretire the deck to study it again.",
        next_lesson=deck_next_lesson(user, slug, deck_data["level_id"]),
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
        complete_url=url_for("api_vocab.level_daily_complete", level_id=level_id),
        exit_url=url_for("pages.level_home", level_id=level_id, tab="vocab"),
        back_label="Back to vocab",
        empty_message="There are no cards to review right now.",
        next_lesson=next_incomplete_lesson(user, level_id),
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
