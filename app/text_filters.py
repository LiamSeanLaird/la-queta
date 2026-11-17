"""Jinja filters for lesson text."""

import re

from markupsafe import Markup, escape

# A word-initial affix such as "-em", "-à", "-er/-re" or the infix "-eix-": a
# hyphen that does not follow a letter, digit or another hyphen, then letters.
# Hyphens inside words ("dilluns-dimarts") and spaced dashes (" - ") are left
# alone.
_AFFIX_RE = re.compile(r"(?<![\w-])-\w+(?:/-\w+)*-?")


def keep_affixes(text: str | None) -> Markup:
    """Escape text and wrap each affix in a nowrap span.

    Browsers may break a line straight after a hyphen, which splits an ending
    like "-em" into "-" and "em" on the next line. The span keeps it whole.
    """
    escaped = str(escape(text or ""))
    return Markup(
        _AFFIX_RE.sub(lambda m: f'<span class="affix">{m.group(0)}</span>', escaped)
    )
