"""Pronunciation respellings follow Central Catalan.

- There is no [v] sound in Central Catalan: written v is said like b,
  so respellings write b, never v.
- The final r of an infinitive is silent (parlar = puhr-LAH), except before
  an attached pronoun (dutxar-se, provar-me'l), where it is sounded.
"""

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# Phrase cards whose infinitive is the last sound of a word in the respelling.
INFINITIVE_PHRASES = {
    "ad_010": "NA",  # demanar
    "ad_012": "PLEE",  # omplir
    "hd028": "feh",  # fer
    "sh_015": "KA",  # embolicar
    "sh_019": "YA",  # ensenyar
    "tr_033": "GA",  # pagar
    "sg_004": "MA",  # fumar
    "soc012": "LA",  # parlar
    "soc013": "TEE",  # repetir
    "soc015": "DA",  # ajudar
    "tr_029": "DA",  # ajudar
    "tr_055": "DA",  # ajudar
}


def _cards():
    for file in sorted((ROOT / "content" / "decks").glob("*.json")):
        data = json.loads(file.read_text(encoding="utf-8"))
        cards = data["cards"] if isinstance(data, dict) else data
        yield from cards


def test_respellings_write_v_as_b():
    offenders = [
        (c["id"], c["pronunciation"])
        for c in _cards()
        if re.search("v", c.get("pronunciation", ""), re.IGNORECASE)
    ]
    assert offenders == []


def test_infinitive_cards_do_not_sound_the_final_r():
    offenders = []
    for card in _cards():
        if card.get("pos") != "verb" or "-" in card["catalan"]:
            continue
        if card["catalan"].endswith("r") and card["pronunciation"].lower().endswith(
            "r"
        ):
            offenders.append((card["id"], card["catalan"], card["pronunciation"]))
    assert offenders == []


def test_infinitives_inside_phrases_do_not_sound_the_final_r():
    by_id = {c["id"]: c for c in _cards()}
    for card_id, syllable in INFINITIVE_PHRASES.items():
        words = re.split(r"[\s-]+", by_id[card_id]["pronunciation"])
        assert syllable in words, (card_id, by_id[card_id]["pronunciation"])
