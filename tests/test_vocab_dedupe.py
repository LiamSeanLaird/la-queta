"""Each Catalan word lives in exactly one deck; merges keep learner progress."""

from __future__ import annotations

import json
import re
import unicodedata
from collections import defaultdict
from pathlib import Path

import pytest
from flask_migrate import downgrade, upgrade
from sqlalchemy import select

from app.extensions import db
from app.models import Card, Deck, User, UserCardProgress
from app.services.seed import seed_all

DECKS = Path(__file__).resolve().parents[1] / "content" / "decks"

# Same spelling, different words. Keep this list short and deliberate.
ALLOWED_HOMOGRAPHS = {
    frozenset({"hl_003", "hl_008"}),  # el CAP (health centre) / el cap (head)
}


def _normalize(catalan: str) -> str:
    text = unicodedata.normalize("NFC", catalan).lower().replace("...", "")
    return re.sub(r"[^\w' ]", "", text).strip()


def test_no_catalan_word_repeats_across_decks():
    by_word: dict[str, list[str]] = defaultdict(list)
    for path in sorted(DECKS.glob("*_deck*.json")):
        for card in json.loads(path.read_text(encoding="utf-8")):
            by_word[_normalize(card["catalan"])].append(f"{path.stem}:{card['id']}")

    repeats = {
        word: refs
        for word, refs in by_word.items()
        if len(refs) > 1
        and frozenset(ref.split(":")[1] for ref in refs) not in ALLOWED_HOMOGRAPHS
    }
    assert repeats == {}


def _user(handle: str) -> User:
    user = User(handle=handle, email=f"{handle}@example.com", password_hash="x")
    db.session.add(user)
    db.session.flush()
    return user


def _add_card(deck_slug: str, external_id: str) -> Card:
    deck_id = db.session.scalar(select(Deck.id).where(Deck.slug == deck_slug))
    card = Card(deck_id=deck_id, external_id=external_id, catalan="x", english="x")
    db.session.add(card)
    db.session.flush()
    return card


def _card(external_id: str) -> Card | None:
    return db.session.scalar(select(Card).where(Card.external_id == external_id))


def _seen(user: User, external_id: str) -> int | None:
    return db.session.scalar(
        select(UserCardProgress.seen)
        .join(Card, Card.id == UserCardProgress.card_id)
        .where(UserCardProgress.user_id == user.id, Card.external_id == external_id)
    )


def test_dedupe_migration_keeps_most_significant_progress(migrated_app):
    with migrated_app.app_context():
        seed_all()
        # Recreate the pre-dedupe duplicates as they exist in production.
        soc002 = _add_card("social_phrases", "soc002")  # gràcies -> greet_008
        sh_012 = _add_card("shopping", "sh_012")  # obert / tancat -> ev_035 + ev_036
        greet_008 = _card("greet_008")
        ev_035 = _card("ev_035")

        higher_on_removed = _user("a")
        higher_on_kept = _user("b")
        only_removed = _user("c")
        db.session.add_all(
            [
                UserCardProgress(user_id=higher_on_removed.id, card_id=greet_008.id, seen=1),
                UserCardProgress(user_id=higher_on_removed.id, card_id=soc002.id, seen=3),
                UserCardProgress(user_id=higher_on_kept.id, card_id=greet_008.id, seen=4),
                UserCardProgress(user_id=higher_on_kept.id, card_id=soc002.id, seen=2),
                UserCardProgress(user_id=only_removed.id, card_id=soc002.id, seen=2),
                UserCardProgress(user_id=only_removed.id, card_id=sh_012.id, seen=3),
                UserCardProgress(user_id=only_removed.id, card_id=ev_035.id, seen=1),
            ]
        )
        db.session.commit()
        removed_ids = [soc002.id, sh_012.id]

        # Re-run the data migration against this state.
        downgrade(revision="c3d4e5f6a7b8")
        upgrade()
        db.session.expire_all()

        assert _card("soc002") is None
        assert _card("sh_012") is None
        assert _seen(higher_on_removed, "greet_008") == 3
        assert _seen(higher_on_kept, "greet_008") == 4
        assert _seen(only_removed, "greet_008") == 2
        assert _seen(only_removed, "ev_035") == 3
        assert _seen(only_removed, "ev_036") == 3
        orphans = db.session.scalars(
            select(UserCardProgress).where(
                UserCardProgress.card_id.in_(removed_ids)
            )
        ).all()
        assert orphans == []

        # Seed is happy with the merged state.
        seed_all()


def test_seed_prunes_removed_cards_without_progress(migrated_app):
    with migrated_app.app_context():
        seed_all()
        _add_card("starter", "gone_001")
        db.session.commit()

        seed_all()

        assert _card("gone_001") is None


def test_seed_refuses_to_drop_studied_cards(migrated_app):
    with migrated_app.app_context():
        seed_all()
        card = _add_card("starter", "gone_002")
        user = _user("d")
        db.session.add(UserCardProgress(user_id=user.id, card_id=card.id, seen=1))
        db.session.commit()

        with pytest.raises(ValueError, match="gone_002"):
            seed_all()
        assert _card("gone_002") is not None
