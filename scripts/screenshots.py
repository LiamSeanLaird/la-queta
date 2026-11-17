"""Walk the learner path in headless Chromium and save screenshots.

Registers a fresh account, then visits each page at phone (390px) and desktop
(1280px) width in light and dark mode. Prints any console errors or failed
requests so JS bugs surface without opening a browser.

Usage (app already running, e.g. on port 5077):

    poetry run python scripts/screenshots.py --base http://127.0.0.1:5077 \
        --out /tmp/la-queta-shots /levels/a1 /decks/starter/study

With no paths, a default learner walk is used. Set PLAYWRIGHT_CHROMIUM to a
Chromium binary if the version Playwright expects is not installed.
"""

from __future__ import annotations

import argparse
import glob
import os
import sys
import uuid
from pathlib import Path

from playwright.sync_api import sync_playwright

DEFAULT_PATHS = [
    "/levels",
    "/levels/a1",
    "/levels/a1?tab=vocab",
    "/lessons/present-tense",
    "/lessons/present-tense?tab=practice",
    "/decks/starter",
    "/decks/starter/study",
    "/decks/starter/browse",
    "/levels/a1/daily",
]

WIDTHS = {"phone": 390, "desktop": 1280}


def _chromium_path() -> str | None:
    explicit = os.environ.get("PLAYWRIGHT_CHROMIUM")
    if explicit:
        return explicit
    # Fall back to any cached Chromium if the pinned one is missing.
    pattern = os.path.expanduser(
        "~/Library/Caches/ms-playwright/chromium-*/chrome-mac*/"
        "*.app/Contents/MacOS/*"
    )
    matches = sorted(glob.glob(pattern))
    return matches[-1] if matches else None


def _slug(path: str) -> str:
    return path.strip("/").replace("/", "_").replace("?", "_").replace("=", "-") or "home"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", default="http://127.0.0.1:5077")
    parser.add_argument("--out", default="/tmp/la-queta-shots")
    parser.add_argument("--dark", action="store_true", help="also capture dark mode")
    parser.add_argument(
        "--viewport", action="store_true", help="capture only the first screen, not the full page"
    )
    parser.add_argument("paths", nargs="*")
    args = parser.parse_args()
    paths = args.paths or DEFAULT_PATHS
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    problems: list[str] = []
    with sync_playwright() as p:
        try:
            browser = p.chromium.launch()
        except Exception:
            browser = p.chromium.launch(executable_path=_chromium_path())
        schemes = ["light", "dark"] if args.dark else ["light"]
        for scheme in schemes:
            for label, width in WIDTHS.items():
                context = browser.new_context(
                    viewport={"width": width, "height": 900},
                    color_scheme=scheme,
                )
                handle = f"shot{uuid.uuid4().hex[:8]}"
                resp = context.request.post(
                    f"{args.base}/api/auth/register",
                    data={
                        "handle": handle,
                        "email": f"{handle}@example.com",
                        "password": "password123",
                    },
                )
                if not resp.ok:
                    print(f"register failed: {resp.status} {resp.text()}", file=sys.stderr)
                    return 1
                page = context.new_page()
                current = {"path": ""}
                page.on(
                    "console",
                    lambda msg: msg.type == "error"
                    and problems.append(f"[{label}/{scheme}] {current['path']}: console {msg.text}"),
                )
                page.on(
                    "pageerror",
                    lambda err: problems.append(f"[{label}/{scheme}] {current['path']}: {err}"),
                )
                page.on(
                    "response",
                    lambda r: r.status >= 400
                    and problems.append(f"[{label}/{scheme}] {current['path']}: HTTP {r.status} {r.url}"),
                )
                for path in paths:
                    current["path"] = path
                    page.goto(f"{args.base}{path}", wait_until="networkidle")
                    file = out / f"{_slug(path)}-{label}-{scheme}.png"
                    page.screenshot(path=str(file), full_page=not args.viewport)
                    print(file)
                context.close()
        browser.close()

    for line in problems:
        print("PROBLEM", line)
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
