from flask import Blueprint, jsonify

from app.services.auth import require_user
from app.services.errors import ServiceError
from app.services.vocab import (
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


@bp.post("/api/cards/<int:card_id>/seen")
def card_seen(card_id: int):
    try:
        user = require_user()
        card = increment_seen(user, card_id)
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
