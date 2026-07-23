from flask import Blueprint, jsonify, request

from app.services.auth import require_user
from app.services.errors import ServiceError
from app.services.lessons import complete_lesson, get_lesson, list_lessons_for_level

bp = Blueprint("api_lessons", __name__)


@bp.get("/api/levels/<level_id>/lessons")
def lessons_for_level(level_id: str):
    try:
        user = require_user()
        lessons = list_lessons_for_level(user, level_id)
    except ServiceError as exc:
        return jsonify({"error": exc.message}), exc.status_code
    return jsonify({"lessons": lessons})


@bp.get("/api/lessons/<lesson_id>")
def lesson_detail(lesson_id: str):
    try:
        user = require_user()
        lesson = get_lesson(user, lesson_id)
    except ServiceError as exc:
        return jsonify({"error": exc.message}), exc.status_code
    return jsonify(lesson)


@bp.post("/api/lessons/<lesson_id>/complete")
def lesson_complete(lesson_id: str):
    payload = request.get_json(silent=True) or {}
    try:
        user = require_user()
        lesson = complete_lesson(
            user,
            lesson_id,
            payload.get("exercises_correct"),
            payload.get("exercises_total"),
        )
    except ServiceError as exc:
        return jsonify({"error": exc.message}), exc.status_code
    return jsonify(lesson)
