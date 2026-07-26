"""Normalize and match practice answers (accents required; punctuation ignored)."""

from __future__ import annotations

import re


_WS = re.compile(r"\s+")
# Keep letters/digits (incl. Catalan accents), spaces, apostrophes, hyphens.
_DROP = re.compile(r"[^\w\s'-]+", re.UNICODE)


def normalize_answer(value: str) -> str:
    text = _DROP.sub("", (value or "").strip())
    return _WS.sub(" ", text).casefold()


def answers_for_item(item: dict) -> list[str]:
    if item.get("answers"):
        return [str(a) for a in item["answers"]]
    if item.get("answer") is not None:
        return [str(item["answer"])]
    return []


def answers_match(user_value: str, accepted: list[str]) -> bool:
    needle = normalize_answer(user_value)
    return any(normalize_answer(item) == needle for item in accepted)
