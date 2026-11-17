"""Word endings like "-em" must not split across lines in lesson text."""

from __future__ import annotations

import re

from app.services.seed import seed_all
from app.text_filters import keep_affixes


def test_wraps_word_initial_affixes():
    out = str(keep_affixes("add endings: -o, -es, -a, -em, -eu, -en"))
    assert re.findall(r'<span class="affix">([^<]*)</span>', out) == [
        "-o",
        "-es",
        "-a",
        "-em",
        "-eu",
        "-en",
    ]
    assert out.endswith('<span class="affix">-en</span>')


def test_keeps_slash_pairs_and_accents_together():
    out = str(keep_affixes("drop -er/-re (-à)"))
    assert '<span class="affix">-er/-re</span>' in out
    assert '(<span class="affix">-à</span>)' in out


def test_keeps_infix_whole():
    assert str(keep_affixes("no -eix-")) == 'no <span class="affix">-eix-</span>'


def test_leaves_inner_hyphens_and_spaced_dashes_alone():
    text = "dilluns-dimarts - a spaced dash, s-a"
    assert str(keep_affixes(text)) == text


def test_escapes_html_and_handles_none():
    assert (
        str(keep_affixes("<b>-em</b>"))
        == '&lt;b&gt;<span class="affix">-em</span>&lt;/b&gt;'
    )
    assert str(keep_affixes(None)) == ""


def test_present_tense_lesson_wraps_endings(migrated_app, migrated_client):
    with migrated_app.app_context():
        seed_all()
    migrated_client.post(
        "/api/auth/register",
        json={
            "handle": "affixer",
            "email": "affixer@example.com",
            "password": "password1",
        },
    )
    html = migrated_client.get("/lessons/present-tense").get_data(as_text=True)
    callouts = re.findall(r'<p class="rule-callout">(.*?)</p>', html, re.S)
    assert callouts
    ar_rule = next(
        c for c in callouts if c.startswith('<span class="affix">-AR</span> verbs')
    )
    for ending in ("-o", "-es", "-a", "-em", "-eu", "-en"):
        assert f'<span class="affix">{ending}</span>' in ar_rule
    assert '<span class="affix">-er/-re</span>' in html
    # No bare word-initial ending is left outside a span in any callout.
    for callout in callouts:
        bare = re.sub(r'<span class="affix">[^<]*</span>', "", callout)
        assert not re.search(r"(?<![\w-])-\w", bare), callout
