"""Guard dark mode in static/app.css.

Every colour is a custom property on :root, and a prefers-color-scheme: dark
block redefines them. A raw colour in an ordinary rule would stay the same in
dark mode (for example white text on a now-light surface), so rules outside
the :root blocks may only use tokens.
"""

import re
from pathlib import Path

CSS_PATH = Path(__file__).resolve().parents[1] / "static" / "app.css"
CSS = CSS_PATH.read_text()

DARK_RE = re.compile(
    r"@media \(prefers-color-scheme: dark\)\s*\{\s*:root\s*\{([^}]*)\}\s*\}"
)
ROOT_RE = re.compile(r"(?m)^:root\s*\{([^}]*)\}")
RAW_COLOUR = re.compile(
    r"#[0-9a-fA-F]{3,8}\b|\brgba?\(|\bhsla?\(|[\s,(]white\b|[\s,(]black\b"
)


def _tokens(block: str) -> dict[str, str]:
    return dict(re.findall(r"(--[\w-]+)\s*:\s*([^;]+);", block))


def _colour_tokens(tokens: dict[str, str]) -> set[str]:
    return {name for name, value in tokens.items() if RAW_COLOUR.search(" " + value)}


def test_dark_block_exists_and_sets_color_scheme():
    assert DARK_RE.search(CSS), (
        "missing @media (prefers-color-scheme: dark) :root block"
    )
    root = ROOT_RE.search(CSS)
    assert root and "color-scheme: light dark" in root.group(1)


def test_every_light_colour_token_has_a_dark_value():
    light = _colour_tokens(_tokens(ROOT_RE.search(CSS).group(1)))
    dark = set(_tokens(DARK_RE.search(CSS).group(1)))
    assert light, "no colour tokens found on :root"
    assert light - dark == set()


def test_dark_mode_changes_surfaces_and_ink():
    light = _tokens(ROOT_RE.search(CSS).group(1))
    dark = _tokens(DARK_RE.search(CSS).group(1))
    for name in (
        "--bg",
        "--bg-elevated",
        "--ink",
        "--muted",
        "--border",
        "--tint-base",
        "--scrim",
    ):
        assert light[name] != dark[name], name


def test_rules_outside_root_use_tokens_not_raw_colours():
    rest = DARK_RE.sub("", CSS)
    rest = ROOT_RE.sub("", rest)
    rest = re.sub(r"/\*.*?\*/", "", rest, flags=re.S)
    offenders = [
        line.strip()
        for line in rest.splitlines()
        if ":" in line and RAW_COLOUR.search(line.split(":", 1)[1])
    ]
    assert offenders == []


def test_theme_color_meta_matches_bg_in_each_scheme():
    base = (CSS_PATH.parents[1] / "templates" / "base.html").read_text()
    light_bg = _tokens(ROOT_RE.search(CSS).group(1))["--bg"]
    dark_bg = _tokens(DARK_RE.search(CSS).group(1))["--bg"]
    assert (
        f'<meta name="theme-color" content="{light_bg}" '
        'media="(prefers-color-scheme: light)">' in base
    )
    assert (
        f'<meta name="theme-color" content="{dark_bg}" '
        'media="(prefers-color-scheme: dark)">' in base
    )


def test_link_tabs_keep_the_idle_tab_colour():
    # a.tab-btn outranks .tab-btn, so a colour there would hide which tab is active.
    for block in re.findall(r"([^{}]*a\.tab-btn[^{}]*)\{([^}]*)\}", CSS):
        assert not re.search(r"(?m)^\s*color\s*:", block[1]), block[0].strip()
