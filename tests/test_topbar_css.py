"""Guard the logged-in topbar layout in static/app.css.

The account and feedback buttons used to stack in a column inside a 2.75rem
side column, which made the header two buttons tall and left the icons hanging
below the brand line at every width.
"""

import re
from pathlib import Path

CSS = (Path(__file__).resolve().parents[1] / "static" / "app.css").read_text()


def _rule(selector: str) -> str:
    match = re.search(r"(?m)^" + re.escape(selector) + r"\s*\{([^}]*)\}", CSS)
    assert match, f"no rule for {selector}"
    return match.group(1)


def test_topbar_actions_sit_in_one_row():
    rule = _rule(".topbar__actions")
    assert "display: flex" in rule
    assert "flex-direction: column" not in rule


def test_topbar_sides_share_space_so_brand_stays_centred():
    rule = _rule(".topbar")
    assert "grid-template-columns: minmax(0, 1fr) auto minmax(0, 1fr)" in rule
