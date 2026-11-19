"""Phase 9 — lesson practice banks, matching, complete gate."""

from __future__ import annotations

from app.services.practice_match import (
    answers_for_item,
    normalize_answer,
    answers_match,
)
from app.services.seed import seed_all


def _register(client, handle: str = "liam"):
    slug = "".join(handle.lower().split())
    response = client.post(
        "/api/auth/register",
        json={
            "handle": handle,
            "email": f"{slug}@example.com",
            "password": "password1",
        },
    )
    assert response.status_code == 201
    return response.get_json()


def test_normalize_keeps_accents():
    assert normalize_answer("  La  Taula ") == "la taula"
    assert normalize_answer("ESTACIÓ") == "estació"
    assert normalize_answer("estacio") != normalize_answer("estació")


def test_normalize_ignores_punctuation_and_case():
    assert normalize_answer("Com estàs?") == "com estàs"
    assert normalize_answer("com estàs") == "com estàs"
    assert normalize_answer("«Gràcies!»") == "gràcies"
    assert normalize_answer("l'estació.") == "l'estació"
    assert answers_match("com estàs", ["Com estàs?"])
    assert answers_match("Com estas?", ["Com estàs?"]) is False  # accent required


def test_answers_match_list():
    assert answers_match("la taula", ["la taula", "La Taula"])
    assert not answers_match("la tabla", ["la taula"])


def test_seed_practice_no_inline_exercises(migrated_app, migrated_client):
    with migrated_app.app_context():
        seed_all()
    _register(migrated_client)

    body = migrated_client.get("/api/lessons/noun-gender").get_json()
    assert all(section["type"] != "exercise" for section in body["sections"])
    practice = body["practice"]
    assert len(practice) >= 8
    kinds = {item["kind"] for item in practice}
    assert "multiple_choice" in kinds
    assert "cloze" in kinds
    assert "type_in" in kinds
    assert sum(1 for item in practice if item["kind"] == "cloze") >= 2
    assert sum(1 for item in practice if item["kind"] == "type_in") >= 2


def test_complete_requires_full_practice_bank(migrated_app, migrated_client):
    with migrated_app.app_context():
        seed_all()
    _register(migrated_client)

    practice = migrated_client.get("/api/lessons/noun-gender").get_json()["practice"]
    total = len(practice)

    bad = migrated_client.post(
        "/api/lessons/noun-gender/complete",
        json={"exercises_correct": 4, "exercises_total": 4},
    )
    assert bad.status_code == 400

    ok = migrated_client.post(
        "/api/lessons/noun-gender/complete",
        json={"exercises_correct": total, "exercises_total": total},
    )
    assert ok.status_code == 200
    assert ok.get_json()["completed"] is True


def test_lesson_page_has_learn_test_tabs(migrated_app, migrated_client):
    with migrated_app.app_context():
        seed_all()
    _register(migrated_client)

    page = migrated_client.get("/lessons/noun-gender")
    assert page.status_code == 200
    assert b">Test</a" in page.data
    assert b"tab=test" in page.data
    assert b"complete-lesson" not in page.data
    assert b">Take the test</a>" in page.data

    practice_tab = migrated_client.get("/lessons/noun-gender?tab=test")
    assert practice_tab.status_code == 200
    assert b"js/practice.js" in practice_tab.data
    assert b'data-tab="test"' in practice_tab.data
    assert b"is-active" in practice_tab.data
    from pathlib import Path

    src = (
        Path(migrated_app.root_path)
        .parent.joinpath("static/js/practice.js")
        .read_text()
    )
    assert "Fill the blank only" in src
    assert "Show answer" in src


def test_answers_for_item_helpers():
    assert answers_for_item({"kind": "type_in", "answers": ["la taula"]}) == [
        "la taula"
    ]
    assert answers_for_item({"kind": "cloze", "answer": "la"}) == ["la"]
    assert answers_for_item({"kind": "multiple_choice", "answer": "el"}) == ["el"]


def test_curly_apostrophe_matches_straight_answer():
    # iPhone keyboards turn ' into ’ by default; both must match the answer.
    assert answers_match("l’estació", ["l'estació"])
    assert answers_match("D’acord", ["D'acord."])
    assert answers_match("l'estació", ["l’estació"])
    assert not answers_match("lestació", ["l'estació"])


def test_practice_js_treats_curly_apostrophe_as_straight(migrated_app):
    import json
    import re
    import shutil
    import subprocess
    from pathlib import Path

    import pytest

    node = shutil.which("node")
    if node is None:
        pytest.skip("node is not installed")
    src = (
        Path(migrated_app.root_path)
        .parent.joinpath("static/js/practice.js")
        .read_text()
    )
    match = re.search(r"  function normalizeAnswer\(value\) \{.*?\n  \}\n", src, re.S)
    assert match, "normalizeAnswer not found in practice.js"
    inputs = ["l’estació", "l'estació", "D’acord.", "M‘agrada llegir"]
    script = (
        match.group(0)
        + f"console.log(JSON.stringify({json.dumps(inputs)}.map(normalizeAnswer)));"
    )
    out = subprocess.run(
        [node, "-e", script], capture_output=True, text=True, check=True
    )
    assert json.loads(out.stdout) == [
        "l'estació",
        "l'estació",
        "d'acord",
        "m'agrada llegir",
    ]
