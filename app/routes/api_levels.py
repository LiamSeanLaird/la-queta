from flask import Blueprint, jsonify

from app.services.errors import ServiceError
from app.services.auth import require_user, user_to_dict
from app.services.levels import list_levels_for_user, select_level

bp = Blueprint("api_levels", __name__)


@bp.get("/api/levels")
def levels():
    try:
        user = require_user()
    except ServiceError as exc:
        return jsonify({"error": exc.message}), exc.status_code
    return jsonify({"levels": list_levels_for_user(user)})


@bp.post("/api/levels/<level_id>/select")
def select(level_id: str):
    try:
        user = require_user()
        user = select_level(user, level_id)
    except ServiceError as exc:
        return jsonify({"error": exc.message}), exc.status_code
    return jsonify(user_to_dict(user))
