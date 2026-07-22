import random
from flask import Flask, jsonify, render_template, abort
from store import list_decks, load_cards, list_lessons, load_lesson

app = Flask(__name__)


@app.route("/")
def index():
    return render_template("index.html")


# ── Vocab ─────────────────────────────────────────────────

@app.route("/api/decks")
def decks():
    return jsonify(list_decks())


@app.route("/api/decks/<slug>/cards")
def cards(slug):
    result = load_cards(slug)
    if result is None:
        abort(404)
    return jsonify(result)


@app.route("/api/decks/<slug>/session")
def session(slug):
    result = load_cards(slug)
    if result is None:
        abort(404)
    cards = list(result)
    random.shuffle(cards)
    return jsonify(cards)


# ── Lessons ───────────────────────────────────────────────

@app.route("/api/lessons")
def lessons():
    return jsonify(list_lessons())


@app.route("/api/lessons/<lesson_id>")
def lesson(lesson_id):
    result = load_lesson(lesson_id)
    if result is None:
        abort(404)
    return jsonify(result)


if __name__ == "__main__":
    import os
    port = int(os.environ.get("PORT", 5001))
    debug = os.environ.get("FLASK_ENV") != "production"
    app.run(host="0.0.0.0", port=port, debug=debug)
