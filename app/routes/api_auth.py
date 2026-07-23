from flask import Blueprint, jsonify, request

from app.services.auth import (
    AuthError,
    authenticate_user,
    login_user,
    logout_user,
    register_user,
    require_user,
    user_to_dict,
)

bp = Blueprint("api_auth", __name__)


@bp.post("/api/auth/register")
def register():
    payload = request.get_json(silent=True) or {}
    try:
        user = register_user(
            payload.get("handle"),
            payload.get("email"),
            payload.get("password"),
        )
    except AuthError as exc:
        return jsonify({"error": exc.message}), exc.status_code

    login_user(user)
    return jsonify(user_to_dict(user)), 201


@bp.post("/api/auth/login")
def login():
    payload = request.get_json(silent=True) or {}
    try:
        user = authenticate_user(payload.get("email"), payload.get("password"))
    except AuthError as exc:
        return jsonify({"error": exc.message}), exc.status_code

    login_user(user)
    return jsonify(user_to_dict(user))


@bp.post("/api/auth/logout")
def logout():
    logout_user()
    return "", 204


@bp.get("/api/me")
def me():
    try:
        user = require_user()
    except AuthError as exc:
        return jsonify({"error": exc.message}), exc.status_code
    return jsonify(user_to_dict(user))
