"""Phase 5 — vocab decks, session, seen, browse."""

from __future__ import annotations

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



def test_seed_decks_into_a1(migrated_app):
    with migrated_app.app_context():
        seed_all()
        from sqlalchemy import func, select

        from app.extensions import db
        from app.models import Card, Deck

        assert db.session.scalar(select(func.count()).select_from(Deck)) == 18
        assert db.session.scalar(select(func.count()).select_from(Card)) == 382
        a2_decks = db.session.scalar(
            select(func.count()).select_from(Deck).where(Deck.level_id == "a2")
        )
        assert a2_decks == 0


def test_every_deck_file_has_a_distinct_title():
    from app.services.seed import CONTENT, DECK_TITLES, _deck_slug_from_filename

    slugs = {_deck_slug_from_filename(p.name) for p in (CONTENT / "decks").glob("*_deck*.json")}
    assert slugs == set(DECK_TITLES)
    titles = list(DECK_TITLES.values())
    assert len(set(titles)) == len(titles)
    for title in titles:
        # Titles are written by hand, not derived from the file slug.
        assert "_" not in title
        assert "\u2014" not in title


def _deck_cards(slug: str) -> list[dict]:
    import json

    from app.services.seed import CONTENT

    return json.loads((CONTENT / "decks" / f"{slug}_deck.json").read_text(encoding="utf-8"))


def _lesson_deck(lesson_id: str) -> str | None:
    """The `deck` field of a lesson, looked up by id (file names carry the order)."""
    import json

    from app.services.seed import CONTENT

    for path in (CONTENT / "lessons").glob("*.json"):
        raw = json.loads(path.read_text(encoding="utf-8"))
        if raw["id"] == lesson_id:
            return raw.get("deck")
    raise AssertionError(f"no lesson {lesson_id}")


def test_describing_words_deck_is_adjectives_with_both_genders():
    cards = _deck_cards("everyday")
    assert 20 <= len(cards) <= 30
    for card in cards:
        assert card["pos"] == "adjective", card["id"]
        # Show both genders where they differ, or say the form is shared.
        assert " / " in card["catalan"] or card["hint"] == "same m/f form", card["id"]


def test_food_lessons_point_to_food_and_drink_deck():
    cards = _deck_cards("food_drink")
    assert 20 <= len(cards) <= 30
    assert all("food" in card["tags"] for card in cards)
    for lesson in ("definite-articles", "food-cafe"):
        assert _lesson_deck(lesson) == "food_drink"


def test_travel_and_directions_are_separate_one_topic_decks():
    travel = _deck_cards("travel")
    directions = _deck_cards("directions")
    assert 20 <= len(travel) <= 30
    assert 20 <= len(directions) <= 30
    assert _lesson_deck("directions") == "directions"
    assert _lesson_deck("travel-transport") == "travel"

    # Places and way-finding live in Places & Directions, not Travel & Transport.
    travel_words = {card["catalan"] for card in travel}
    assert {"el museu", "el nord", "tot recte", "aquí"}.isdisjoint(travel_words)
    assert {"el museu", "el nord", "tot recte", "aquí"} <= {c["catalan"] for c in directions}
    # Health and payment phrases moved to their topic decks.
    assert "Truca a un metge!" in {c["catalan"] for c in _deck_cards("health")}
    shopping = {c["catalan"] for c in _deck_cards("shopping")}
    assert {"Puc pagar amb targeta?", "l'efectiu", "el canvi"} <= shopping


def test_greetings_and_polite_phrases_are_separate_one_topic_decks():
    greetings = _deck_cards("starter")
    phrases = _deck_cards("social_phrases")
    assert 20 <= len(greetings) <= 30
    assert 20 <= len(phrases) <= 30
    assert all(card["tags"] == ["greetings"] for card in greetings)
    assert all(card["tags"] == ["phrases"] for card in phrases)
    assert _lesson_deck("introductions") == "starter"
    assert _lesson_deck("question-words") == "social_phrases"

    greeting_words = {card["catalan"] for card in greetings}
    phrase_words = {card["catalan"] for card in phrases}
    assert {"Bon dia", "Em dic...", "Fins demà", "Estic bé"} <= greeting_words
    assert {"Gràcies", "Perdoni", "No entenc", "Pots repetir?"} <= phrase_words
    # Meal phrases and hunger/thirst live in Food & Drink.
    food = {card["catalan"] for card in _deck_cards("food_drink")}
    assert {"Tinc gana", "Tinc set", "Bon profit!", "Estava molt bo"} <= food
    # Short social messages are not signs.
    assert "Fins demà" not in {card["catalan"] for card in _deck_cards("signs")}


def test_seed_rejects_deck_without_title(migrated_app, monkeypatch):
    import pytest

    from app.services import seed

    monkeypatch.delitem(seed.DECK_TITLES, "family")
    with migrated_app.app_context():
        seed.seed_levels()
        with pytest.raises(ValueError, match="family"):
            seed.seed_decks()


def test_list_decks_requires_auth(migrated_client):
    assert migrated_client.get("/api/levels/a1/decks").status_code == 401


def test_list_a1_decks_and_empty_a2(migrated_app, migrated_client):
    with migrated_app.app_context():
        seed_all()
    _register(migrated_client)

    a1 = migrated_client.get("/api/levels/a1/decks")
    assert a1.status_code == 200
    decks = a1.get_json()["decks"]
    assert len(decks) == 18
    # Decks follow the lesson order: lesson 1 (noun-gender) links to everyday.
    assert decks[0]["slug"] == "everyday"
    assert decks[0]["title"] == "Describing Words"
    assert decks[0]["total"] > 0
    assert decks[0]["retired"] == 0
    assert decks[0]["remaining"] == decks[0]["total"]

    a2 = migrated_client.get("/api/levels/a2/decks")
    assert a2.status_code == 200
    assert a2.get_json()["decks"] == []


def test_session_excludes_retired_cards(migrated_app, migrated_client):
    with migrated_app.app_context():
        seed_all()
    _register(migrated_client)

    cards = migrated_client.get("/api/decks/starter/cards").get_json()["cards"]
    first = cards[0]
    for _ in range(3):
        seen = migrated_client.post(f"/api/cards/{first['id']}/seen")
        assert seen.status_code == 200
    assert seen.get_json()["seen"] == 3
    assert seen.get_json()["retired"] is True

    session = migrated_client.get("/api/decks/starter/session").get_json()["cards"]
    assert all(card["id"] != first["id"] for card in session)
    assert len(session) == len(cards) - 1


def test_browse_includes_seen(migrated_app, migrated_client):
    with migrated_app.app_context():
        seed_all()
    _register(migrated_client)
    cards = migrated_client.get("/api/decks/starter/cards").get_json()["cards"]
    assert cards[0]["seen"] == 0
    migrated_client.post(f"/api/cards/{cards[0]['id']}/seen")
    cards = migrated_client.get("/api/decks/starter/cards").get_json()["cards"]
    assert cards[0]["seen"] == 1


def test_card_payload_includes_prototype_meta(migrated_app, migrated_client):
    with migrated_app.app_context():
        seed_all()
    _register(migrated_client)

    starter = migrated_client.get("/api/decks/starter/cards").get_json()["cards"]
    bon_dia = next(c for c in starter if c["external_id"] == "greet_001")
    assert bon_dia["pronunciation"] == "bohn DEE-ah"
    assert bon_dia["pos"] == "phrase"
    assert bon_dia["tags"] == ["greetings"]
    assert bon_dia["forms"] == []

    days = migrated_client.get("/api/decks/days_months/cards").get_json()["cards"]
    dilluns = next(c for c in days if c["external_id"] == "dm_001")
    assert dilluns["gender"] == "m"
    assert dilluns["plural"] == "dilluns"
    assert dilluns["pos"] == "noun"

    browse = migrated_client.get("/decks/days_months/browse")
    assert browse.status_code == 200
    assert b"masculine" in browse.data
    assert b"dee-YOONS" in browse.data


def test_retire_marks_card_and_excludes_from_session(migrated_app, migrated_client):
    with migrated_app.app_context():
        seed_all()
    _register(migrated_client)

    cards = migrated_client.get("/api/decks/starter/cards").get_json()["cards"]
    first = cards[0]
    assert first["retired"] is False

    retired = migrated_client.post(f"/api/cards/{first['id']}/retire")
    assert retired.status_code == 200
    body = retired.get_json()
    assert body["retired"] is True
    assert body["seen"] >= 3

    session = migrated_client.get("/api/decks/starter/session").get_json()["cards"]
    assert all(card["id"] != first["id"] for card in session)

    browse = migrated_client.get("/decks/starter/browse")
    assert browse.status_code == 200
    assert b"Retired" in browse.data
    assert b"data-retire" in browse.data


def test_unretire_deck_resets_seen_and_restores_session(migrated_app, migrated_client):
    with migrated_app.app_context():
        seed_all()
    _register(migrated_client)

    cards = migrated_client.get("/api/decks/starter/cards").get_json()["cards"]
    for card in cards:
        assert migrated_client.post(f"/api/cards/{card['id']}/retire").status_code == 200

    session = migrated_client.get("/api/decks/starter/session").get_json()["cards"]
    assert session == []

    deck_page = migrated_client.get("/decks/starter")
    assert deck_page.status_code == 200
    assert b"Unretire deck" in deck_page.data
    assert b"data-unretire" in deck_page.data

    unretire = migrated_client.post("/api/decks/starter/unretire")
    assert unretire.status_code == 200
    body = unretire.get_json()
    assert body["retired"] == 0
    assert body["remaining"] == body["total"] == len(cards)

    restored = migrated_client.get("/api/decks/starter/cards").get_json()["cards"]
    assert all(card["seen"] == 0 and card["retired"] is False for card in restored)
    session = migrated_client.get("/api/decks/starter/session").get_json()["cards"]
    assert len(session) == len(cards)


def test_core_verbs_deck_has_full_present_tense(migrated_app, migrated_client):
    with migrated_app.app_context():
        seed_all()
    _register(migrated_client)

    cards = migrated_client.get("/api/decks/core_verbs/cards").get_json()["cards"]
    by_word = {card["catalan"]: card for card in cards}
    for verb in ("ser", "estar", "tenir", "anar", "fer", "voler", "poder", "saber", "dir"):
        assert verb in by_word
    persons = ["jo ", "tu ", "ell/ella ", "nosaltres ", "vosaltres ", "ells/elles "]
    for card in cards:
        assert card["pos"] == "verb"
        assert len(card["forms"]) == 6
        assert [form.startswith(p) for form, p in zip(card["forms"], persons)] == [True] * 6
    assert by_word["ser"]["forms"][0] == "jo soc"


def test_browse_shows_verb_forms_in_text_column(migrated_app, migrated_client):
    with migrated_app.app_context():
        seed_all()
    _register(migrated_client)

    html = migrated_client.get("/decks/core_verbs/browse").get_data(as_text=True)
    forms = '<p class="vocab-forms">jo soc · tu ets · ell/ella és'
    assert forms in html
    # Forms sit in the wrapping text column, not the fixed-width meta column.
    row = html[html.index('data-card-id'):]
    assert row.index(forms) < row.index('class="vocab-meta"')


def test_browse_shows_grammar_pills_in_text_column(migrated_app, migrated_client):
    """Noun pills used to sit in the fixed meta column and squeeze the text at phone width."""
    with migrated_app.app_context():
        seed_all()
    _register(migrated_client)

    html = migrated_client.get("/decks/family/browse").get_data(as_text=True)
    row_start = html.index('data-card-id')
    row = html[row_start:html.index('data-card-id', row_start + 1)]
    pills = row.index('class="gram-pills vocab-gram"')
    assert 'gram-pill--pos">noun' in row
    assert row.index('class="vocab-main"') < pills < row.index('class="vocab-meta"')
    meta = row[row.index('class="vocab-meta"'):]
    assert "gram-pill" not in meta
