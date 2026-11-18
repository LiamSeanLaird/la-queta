from flask import Blueprint, jsonify, request

from app.services.auth import require_user
from app.services.daily import record_daily_done
from app.services.errors import ServiceError
from app.services.vocab import (
    daily_session_for_level,
    grade_card,
    increment_seen,
    list_cards_for_deck,
    list_decks_for_level,
    retire_card,
    session_for_deck,
    unretire_deck,
)

bp = Blueprint("api_vocab", __name__)


@bp.get("/api/levels/<level_id>/decks")
def decks_for_level(level_id: str):
    try:
        user = require_user()
        decks = list_decks_for_level(user, level_id)
    except ServiceError as exc:
        return jsonify({"error": exc.message}), exc.status_code
    return jsonify({"decks": decks})


@bp.get("/api/decks/<slug>/cards")
def deck_cards(slug: str):
    try:
        user = require_user()
        cards = list_cards_for_deck(user, slug)
    except ServiceError as exc:
        return jsonify({"error": exc.message}), exc.status_code
    return jsonify({"cards": cards})


@bp.get("/api/decks/<slug>/session")
def deck_session(slug: str):
    try:
        user = require_user()
        cards = session_for_deck(user, slug)
    except ServiceError as exc:
        return jsonify({"error": exc.message}), exc.status_code
    return jsonify({"cards": cards})


@bp.get("/api/levels/<level_id>/daily")
def level_daily(level_id: str):
    try:
        user = require_user()
        cards = daily_session_for_level(user, level_id)
    except ServiceError as exc:
        return jsonify({"error": exc.message}), exc.status_code
    return jsonify({"cards": cards})


@bp.post("/api/levels/<level_id>/daily/complete")
def level_daily_complete(level_id: str):
    """The learner reached "Session complete" on daily vocab.

    Body: {"timezone": "<IANA name>"}; unknown or missing falls back to UTC.
    """
    payload = request.get_json(silent=True) or {}
    try:
        user = require_user()
        status = record_daily_done(user, level_id, payload.get("timezone"))
    except ServiceError as exc:
        return jsonify({"error": exc.message}), exc.status_code
    return jsonify(status)


@bp.post("/api/cards/<int:card_id>/seen")
def card_seen(card_id: int):
    try:
        user = require_user()
        card = increment_seen(user, card_id)
    except ServiceError as exc:
        return jsonify({"error": exc.message}), exc.status_code
    return jsonify(card)


@bp.post("/api/cards/<int:card_id>/grade")
def card_grade(card_id: int):
    """Self-grade after a flip. Body: {"grade": "knew" | "not_yet"}."""
    payload = request.get_json(silent=True) or {}
    try:
        user = require_user()
        card = grade_card(user, card_id, payload.get("grade"))
    except ServiceError as exc:
        return jsonify({"error": exc.message}), exc.status_code
    return jsonify(card)


@bp.post("/api/cards/<int:card_id>/retire")
def card_retire(card_id: int):
    try:
        user = require_user()
        card = retire_card(user, card_id)
    except ServiceError as exc:
        return jsonify({"error": exc.message}), exc.status_code
    return jsonify(card)


@bp.post("/api/decks/<slug>/unretire")
def deck_unretire(slug: str):
    try:
        user = require_user()
        stats = unretire_deck(user, slug)
    except ServiceError as exc:
        return jsonify({"error": exc.message}), exc.status_code
    return jsonify(stats)
