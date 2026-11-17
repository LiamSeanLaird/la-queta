"""Noun cards follow one format: article on the word, gender set, plural with its article."""

from __future__ import annotations

import json
from pathlib import Path

DECKS = Path(__file__).resolve().parents[1] / "content" / "decks"

# The hidden "no plural" marker (months, uncountables).
NO_PLURAL = "—"

# Day and month names are taught bare (dilluns, gener), and signs show the word
# as printed on the sign (Sortida), so these cards may omit the article.
BARE_NOUN_TAGS = {"days", "months", "signs"}

PLURAL_ARTICLE = {"m": "els ", "f": "les "}
SINGULAR_ARTICLE_GENDER = {"el ": "m", "la ": "f"}


def _nouns():
    for path in sorted(DECKS.glob("*_deck*.json")):
        for card in json.loads(path.read_text(encoding="utf-8")):
            if card.get("pos") == "noun":
                yield path.name, card


def test_every_noun_has_a_gender_and_a_plural():
    for name, card in _nouns():
        assert card.get("gender") in ("m", "f"), (name, card["id"], card.get("gender"))
        assert card.get("plural"), (name, card["id"])


def test_noun_plurals_carry_the_article_that_matches_the_gender():
    for name, card in _nouns():
        plural = card["plural"]
        if plural == NO_PLURAL:
            continue
        expected = PLURAL_ARTICLE[card["gender"]]
        assert plural.startswith(expected), (name, card["id"], plural, f"expected '{expected}...'")


def test_nouns_carry_their_article_unless_days_months_or_signs():
    for name, card in _nouns():
        if BARE_NOUN_TAGS & set(card.get("tags", [])):
            continue
        word = card["catalan"]
        assert word.startswith(("el ", "la ", "l'", "els ", "les ")), (name, card["id"], word)


def test_singular_article_matches_the_gender():
    for name, card in _nouns():
        word = card["catalan"]
        for article, gender in SINGULAR_ARTICLE_GENDER.items():
            if word.startswith(article):
                assert card["gender"] == gender, (name, card["id"], word, card["gender"])


# Every card's part of speech comes from this fixed set, so the browse page's
# pill labels and the noun format checks above stay consistent.
ALLOWED_POS = {
    "noun",
    "verb",
    "adjective",
    "adverb",
    "pronoun",
    "number",
    "interjection",
    "phrase",
}


def _cards():
    for path in sorted(DECKS.glob("*_deck*.json")):
        for card in json.loads(path.read_text(encoding="utf-8")):
            yield path.name, card


def test_every_card_has_a_pos_from_the_fixed_set():
    for name, card in _cards():
        assert card.get("pos") in ALLOWED_POS, (name, card["id"], card.get("pos"))


def test_article_led_cards_are_nouns():
    # A lowercase article starts a noun ("la data de naixement"), while a
    # capitalised one starts a sentence ("El meu NIE és..."), which stays a phrase.
    for name, card in _cards():
        if card["catalan"].startswith(("el ", "la ", "l'", "els ", "les ")):
            assert card["pos"] == "noun", (
                name,
                card["id"],
                card["catalan"],
                card["pos"],
            )
