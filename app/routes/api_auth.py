from flask import Blueprint, jsonify, request

from app.services.auth import AuthError, login_user, register_user, require_user, user_to_dict

bp = Blueprint("api_auth", __name__)


@bp.post("/api/auth/register")
def register():
    payload = request.get_json(silent=True) or {}
    try:
        user = register_user(payload.get("handle"))
    except AuthError as exc:
        return jsonify({"error": exc.message}), exc.status_code

    login_user(user)
    return jsonify(user_to_dict(user)), 201


@bp.get("/api/me")
def me():
    try:
        user = require_user()
    except AuthError as exc:
        return jsonify({"error": exc.message}), exc.status_code
    return jsonify(user_to_dict(user))
