"""Render static/og-image.png (1200x630) from scripts/og_image/og-image.html.

The share image is the brand, the "aprèn català" accent line and the
positioning line. Edit the HTML, then regenerate:

    poetry run python scripts/og_image.py

Fonts come from Google Fonts, so this needs network access. The script fails
instead of writing an image if Fraunces or Figtree did not load. Set
PLAYWRIGHT_CHROMIUM to a Chromium binary if the version Playwright expects is
not installed.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "scripts" / "og_image" / "og-image.html"
TARGET = ROOT / "static" / "og-image.png"
WIDTH, HEIGHT = 1200, 630
FONTS = ["Fraunces", "Figtree"]
LOADED_JS = """(family) => Array.from(document.fonts).some(
    (f) => f.family.replace(/"/g, "") === family && f.status === "loaded"
)"""

sys.path.insert(0, str(ROOT / "scripts"))
from screenshots import _chromium_path  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default=str(TARGET))
    args = parser.parse_args()

    with sync_playwright() as p:
        try:
            browser = p.chromium.launch()
        except Exception:
            browser = p.chromium.launch(executable_path=_chromium_path())
        page = browser.new_page(
            viewport={"width": WIDTH, "height": HEIGHT}, device_scale_factor=1
        )
        page.goto(SOURCE.as_uri(), wait_until="networkidle")
        page.evaluate("document.fonts.ready")
        missing = [font for font in FONTS if not page.evaluate(LOADED_JS, font)]
        if missing:
            print(f"fonts did not load: {missing}", file=sys.stderr)
            browser.close()
            return 1
        page.screenshot(
            path=args.out, clip={"x": 0, "y": 0, "width": WIDTH, "height": HEIGHT}
        )
        browser.close()
    print(args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
