"""Content checks for the first two lessons, where most learners start."""

from __future__ import annotations

import json
import re
from pathlib import Path

LESSONS = Path(__file__).resolve().parent.parent / "content" / "lessons"


def _lesson(name: str) -> dict:
    return json.loads((LESSONS / name).read_text(encoding="utf-8"))


def _text(lesson: dict) -> str:
    parts = []
    for section in lesson["sections"]:
        parts.append(section.get("content", ""))
        for item in section.get("items", []):
            parts.append(item["catalan"])
    return "\n".join(parts)


def test_noun_gender_teaches_un_and_una_before_using_them():
    lesson = _lesson("01-noun-gender.json")
    first_un = next(
        i
        for i, section in enumerate(lesson["sections"])
        if any(item["catalan"].startswith("un ") for item in section.get("items", []))
    )
    teaching = lesson["sections"][first_un - 1]
    assert teaching["type"] == "text"
    assert "un " in teaching["content"] and "una " in teaching["content"]
    assert any(item.get("answer") == "una" for item in lesson["practice"])


def test_definite_articles_plural_rule_is_correct():
    lesson = _lesson("02-definite-articles.json")
    text = _text(lesson)
    assert "wait" not in text
    assert "la taula → les taules" in text
    assert "-a change it to -es" in text
    assert "la universitat" in text
    answers = {a for item in lesson["practice"] for a in item.get("answers", [])}
    assert "les taules" in answers


def test_practice_ids_are_unique_across_lessons():
    ids = [
        item["id"]
        for path in sorted(LESSONS.glob("*.json"))
        for item in json.loads(path.read_text(encoding="utf-8"))["practice"]
    ]
    assert len(ids) == len(set(ids))


def test_ser_vs_estar_uses_ser_for_where_places_are():
    lesson = _lesson("03-ser-vs-estar.json")
    notes = {
        item["catalan"]: item.get("note", "")
        for section in lesson["sections"]
        for item in section.get("items", [])
    }
    assert notes["On ets?"].endswith("- ser")
    assert notes["On és l'estació?"].endswith("- ser")
    station = next(item for item in lesson["practice"] if item["id"] == "se-p03")
    assert station["answer"] == "On és l'estació? (ser)"
    for item in lesson["practice"]:
        if item["kind"] == "multiple_choice":
            assert item["answer"] in item["options"]


def test_present_tense_rules_match_their_examples():
    lesson = _lesson("04-present-tense.json")
    text = _text(lesson)
    # The -er/-re model verb follows the stated endings: perd has no ending.
    for form in ["perdo", "perds", "perd", "perdem", "perdeu", "perden"]:
        assert form in text.split("\n")
    # Most -ir verbs take -eix-, except in the we and you-all forms.
    for form in ["llegeixo", "llegeixes", "llegeix", "llegim", "llegiu", "llegeixen"]:
        assert form in text.split("\n")
    notes = {
        item["catalan"]: item.get("note", "")
        for section in lesson["sections"]
        for item in section.get("items", [])
    }
    assert "formal" not in notes["parleu"] or "informal" in notes["parleu"]
    assert "vostè" in notes["parla"]
    answers = {item.get("answer") for item in lesson["practice"]}
    assert {"perd", "llegeixo", "llegim"} <= answers


def test_question_words_teaches_agreement_and_yes_no_questions():
    lesson = _lesson("05-question-words.json")
    text = _text(lesson)
    notes = {
        item["catalan"]: item.get("note", "")
        for section in lesson["sections"]
        for item in section.get("items", [])
    }
    # The t of quant is silent in Central Catalan.
    assert "KWANT" not in notes["quant / quanta?"]
    assert "Quants anys tens?" in text and "Quina hora és?" in text
    assert "Parles anglès?" in text
    assert "usar" not in text and "Pots explicar?" not in text
    answers = {item.get("answer") for item in lesson["practice"]}
    assert {"Quants", "Quina", "Parles anglès?", "Puc fer servir el bany?"} <= answers


def _word_forms(lesson: dict) -> set[str]:
    """Every single Catalan word in a lesson's `words` list, lowercased."""
    forms = set()
    for word in lesson["words"]:
        for part in word["catalan"].replace("/", " ").split():
            forms.add(part.lower())
    return forms


def test_noun_gender_words_cover_everything_the_test_asks_for():
    lesson = _lesson("01-noun-gender.json")
    forms = _word_forms(lesson)
    nouns = [w["catalan"] for w in lesson["words"] if w["catalan"].startswith(("el ", "la "))]
    # Nouns are listed with their article, so the gender is learned with the word.
    assert {"el gat", "la porta", "el cotxe", "la taula", "el pa", "la mà"} <= set(nouns)
    asked = []
    for item in lesson["practice"]:
        asked += item.get("answers", [])
        if item["kind"] == "cloze":
            asked.append(item["answer"])
        if item.get("speak"):
            asked.append(item["speak"])
        if item["kind"] == "multiple_choice" and item["answer"] not in {
            "Masculine",
            "Feminine",
        }:
            asked += item["options"]
        # Words the question names, like 'porta' (door).
        asked += re.findall(r"'([^']+)' \(", item.get("question", ""))
    missing = {
        token
        for phrase in asked
        for token in phrase.lower().split()
        if token not in forms
    }
    assert not missing
    # Every word in the list is also shown in a Learn example.
    examples = _text(lesson).lower()
    for word in lesson["words"]:
        for part in word["catalan"].split(" / "):
            assert part.lower() in examples, part


# Lessons whose `words` list has not been written yet. Each one is audited
# against its test and removed from this set, until the set is empty.
LESSONS_WITHOUT_WORDS = {
    "09-directions.json",
    "10-travel-transport.json",
    "11-food-cafe.json",
    "12-shopping.json",
    "13-health.json",
    "14-signs-messages.json",
    "15-family.json",
    "16-home-routine.json",
    "17-work.json",
    "18-education.json",
    "19-leisure.json",
    "20-public-admin.json",
}

# Grammar words taught in lessons 1 and 2, allowed in any test without being
# listed again in each lesson's words.
GRAMMAR_WORDS = {"el", "la", "els", "les", "l'", "un", "una", "uns", "unes", "i", "de", "d'"}

# Names of people and places spelled the same in English, which a test may use
# without teaching them. Names spelled differently, like Londres, are words.
PROPER_NAMES = {"barcelona", "girona", "marta"}

# Multiple-choice answers that are English, so they ask for no Catalan word.
ENGLISH_ANSWERS = {
    "Masculine",
    "Feminine",
    "It contracts to l'",
    "No - 'parlo' already means 'I speak'",
    "Open",
    "Closed",
    "Free entry",
    "No smoking",
}

_EDGE_PUNCTUATION = ".,;:?!¿¡…«»\"()"


def _tokens(phrase: str) -> list[str]:
    """Lowercased words of a Catalan phrase, with a (ser)-style note removed."""
    phrase = re.sub(r"\([^)]*\)", " ", phrase.replace("’", "'"))
    tokens = []
    for raw in phrase.replace("/", " ").split():
        token = raw.strip(_EDGE_PUNCTUATION).lower()
        if token and token != "-":
            tokens.append(token)
    return tokens


def _asked_phrases(lesson: dict) -> list[str]:
    """Every Catalan phrase the lesson's test asks the learner to produce or recognise."""
    asked = []
    for item in lesson["practice"]:
        asked += item.get("answers", [])
        if item.get("speak"):
            asked.append(item["speak"])
        if item["kind"] == "cloze":
            asked.append(item["answer"])
        if item["kind"] == "multiple_choice" and item["answer"] not in ENGLISH_ANSWERS:
            asked.append(item["answer"])
        # Catalan signs quoted in a question, like «Obert».
        asked += re.findall(r"«([^»]+)»", item.get("question", ""))
    return asked


def _is_taught(token: str, forms: set[str]) -> bool:
    if token in forms or token in GRAMMAR_WORDS or token in PROPER_NAMES:
        return True
    # l'estació is taught if its parts are: the article and estació.
    parts = [p for p in re.split(r"(?<=')|-", token) if p]
    return len(parts) > 1 and all(_is_taught(p, forms) for p in parts)


def _lesson_files() -> list[Path]:
    return sorted(LESSONS.glob("*.json"))


def test_lessons_without_words_are_listed_explicitly():
    names = {path.name for path in _lesson_files()}
    assert LESSONS_WITHOUT_WORDS <= names
    for path in _lesson_files():
        has_words = bool(json.loads(path.read_text(encoding="utf-8")).get("words"))
        assert has_words == (path.name not in LESSONS_WITHOUT_WORDS), path.name


def test_every_test_only_uses_words_its_lesson_teaches():
    for path in _lesson_files():
        if path.name in LESSONS_WITHOUT_WORDS:
            continue
        lesson = json.loads(path.read_text(encoding="utf-8"))
        forms = set()
        for word in lesson["words"]:
            for token in _tokens(word["catalan"]):
                # dues-centes teaches the whole number and each of its parts.
                forms.add(token)
                forms.update(part for part in token.split("-") if part)
        missing = sorted(
            {
                token
                for phrase in _asked_phrases(lesson)
                for token in _tokens(phrase)
                if not _is_taught(token, forms)
            }
        )
        assert not missing, f"{path.name}: {missing}"


def test_every_listed_word_is_shown_on_the_learn_tab():
    for path in _lesson_files():
        lesson = json.loads(path.read_text(encoding="utf-8"))
        learn = _text(lesson).lower().replace("’", "'")
        for word in lesson.get("words", []):
            assert word["english"].strip(), f"{path.name}: {word}"
            for part in word["catalan"].split(" / "):
                assert part.lower() in learn, f"{path.name}: {part}"
