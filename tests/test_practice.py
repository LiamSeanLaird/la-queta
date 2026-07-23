"""Phase 9 — lesson practice banks, matching, complete gate."""

from __future__ import annotations

from app.services.practice_match import answers_for_item, normalize_answer, answers_match
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


def test_lesson_page_has_learn_practice_tabs(migrated_app, migrated_client):
    with migrated_app.app_context():
        seed_all()
    _register(migrated_client)

    page = migrated_client.get("/lessons/noun-gender")
    assert page.status_code == 200
    assert b"Practice" in page.data
    assert b"tab=practice" in page.data
    assert b"complete-lesson" not in page.data
    assert b"Go to Practice" in page.data

    practice_tab = migrated_client.get("/lessons/noun-gender?tab=practice")
    assert practice_tab.status_code == 200
    assert b"js/practice.js" in practice_tab.data
    assert b'data-tab="practice"' in practice_tab.data
    assert b"is-active" in practice_tab.data


def test_answers_for_item_helpers():
    assert answers_for_item({"kind": "type_in", "answers": ["la taula"]}) == ["la taula"]
    assert answers_for_item({"kind": "cloze", "answer": "la"}) == ["la"]
    assert answers_for_item({"kind": "multiple_choice", "answer": "el"}) == ["el"]
