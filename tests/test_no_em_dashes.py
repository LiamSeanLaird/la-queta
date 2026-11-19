"""Learner-facing text and project docs use plain dashes "-", never em dashes.

The one allowed em dash is the deliberate 'no plural' marker: a deck card's
plural field set to exactly "—", which browse.html and study.js hide.
"""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EM_DASH = "—"
NO_PLURAL_MARKER = EM_DASH


def _strings(value, path=""):
    if isinstance(value, str):
        yield path, value
    elif isinstance(value, dict):
        for key, item in value.items():
            yield from _strings(item, f"{path}.{key}")
    elif isinstance(value, list):
        for i, item in enumerate(value):
            yield from _strings(item, f"{path}[{i}]")


def test_lesson_and_deck_content_has_no_em_dashes():
    offenders = []
    files = sorted((ROOT / "content" / "lessons").glob("*.json"))
    files += sorted((ROOT / "content" / "decks").glob("*.json"))
    for file in files:
        data = json.loads(file.read_text(encoding="utf-8"))
        for path, text in _strings(data):
            if path.endswith(".plural") and text == NO_PLURAL_MARKER:
                continue
            if EM_DASH in text:
                offenders.append(f"{file.name}{path}: {text}")
    assert offenders == []


def test_templates_and_page_scripts_have_no_em_dashes_except_plural_check():
    offenders = []
    files = sorted((ROOT / "templates").glob("*.html"))
    files += sorted((ROOT / "static" / "js").glob("*.js"))
    for file in files:
        for lineno, line in enumerate(file.read_text(encoding="utf-8").splitlines(), 1):
            if EM_DASH not in line:
                continue
            # The plural-marker checks compare against the em dash on purpose.
            if "plural" in line and (f"'{EM_DASH}'" in line or f'"{EM_DASH}"' in line):
                continue
            offenders.append(f"{file.relative_to(ROOT)}:{lineno}: {line.strip()}")
    assert offenders == []


def test_docs_app_code_and_scripts_have_no_em_dashes():
    """Project docs, app code, scripts and build files use plain dashes too.

    CHANGELOG.md is auto-generated and prototype/ is frozen, so both are skipped.
    """
    files = [p for p in sorted(ROOT.glob("*.md")) if p.name != "CHANGELOG.md"]
    files += sorted((ROOT / "content").glob("*.md"))
    files += sorted((ROOT / "app").rglob("*.py"))
    files += sorted(p for p in (ROOT / "scripts").iterdir() if p.is_file())
    files += sorted(p for p in (ROOT / "deploy").iterdir() if p.is_file())
    files += [ROOT / "Makefile", ROOT / "pyproject.toml"]
    offenders = []
    for file in files:
        for lineno, line in enumerate(file.read_text(encoding="utf-8").splitlines(), 1):
            if EM_DASH in line:
                offenders.append(f"{file.relative_to(ROOT)}:{lineno}: {line.strip()}")
    assert offenders == []
