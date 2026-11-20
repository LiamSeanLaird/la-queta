"""Render the landing page's lesson screenshot, light and dark.

The landing page (/) shows the first question of lesson 1's test, as a
logged-out visitor sees it on a phone. This script takes that picture from the
running app, so it always matches the real UI:

    poetry run python scripts/landing_screenshot.py --base http://127.0.0.1:5077

The app must be running against a seeded database (see CONTRIBUTING.md). The
script writes static/landing-test-light.png and static/landing-test-dark.png,
both the same size, and fails without writing if the page shows a console
error or a failed request. Set PLAYWRIGHT_CHROMIUM to a Chromium binary if the
version Playwright expects is not installed.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
LESSON_PATH = "/lessons/noun-gender?tab=test"
WIDTH, HEIGHT = 390, 844
SCALE = 2
# Space kept around the lesson heading and the answer options in the crop.
PAD_TOP, PAD_BOTTOM = 24, 32

sys.path.insert(0, str(ROOT / "scripts"))
from screenshots import _chromium_path  # noqa: E402


def _shoot(browser, base: str, scheme: str, out: Path, problems: list[str]) -> None:
    context = browser.new_context(
        viewport={"width": WIDTH, "height": HEIGHT},
        color_scheme=scheme,
        device_scale_factor=SCALE,
    )
    page = context.new_page()
    page.on(
        "console",
        lambda msg: msg.type == "error" and problems.append(f"{scheme}: {msg.text}"),
    )
    page.on("pageerror", lambda err: problems.append(f"{scheme}: {err}"))
    page.on(
        "response",
        lambda r: r.status >= 400 and problems.append(f"{scheme}: HTTP {r.status} {r.url}"),
    )
    page.goto(f"{base}{LESSON_PATH}", wait_until="networkidle")
    page.get_by_role("button", name="Start the test").click()
    page.locator("#practice-item .option").first.wait_for()
    page.evaluate("document.fonts.ready")
    top = page.locator("h1").bounding_box()["y"] - PAD_TOP
    item = page.locator("#practice-item").bounding_box()
    bottom = item["y"] + item["height"] + PAD_BOTTOM
    page.screenshot(
        path=str(out),
        clip={"x": 0, "y": top, "width": WIDTH, "height": bottom - top},
    )
    context.close()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", default="http://127.0.0.1:5077")
    parser.add_argument("--out-dir", default=str(ROOT / "static"))
    args = parser.parse_args()
    out_dir = Path(args.out_dir)
    tmp_dir = out_dir / ".landing-shot-tmp"
    tmp_dir.mkdir(parents=True, exist_ok=True)

    problems: list[str] = []
    with sync_playwright() as p:
        try:
            browser = p.chromium.launch()
        except Exception:
            browser = p.chromium.launch(executable_path=_chromium_path())
        for scheme in ("light", "dark"):
            _shoot(browser, args.base, scheme, tmp_dir / f"{scheme}.png", problems)
        browser.close()

    if problems:
        for line in problems:
            print("PROBLEM", line, file=sys.stderr)
        for file in tmp_dir.iterdir():
            file.unlink()
        tmp_dir.rmdir()
        return 1
    for scheme in ("light", "dark"):
        target = out_dir / f"landing-test-{scheme}.png"
        (tmp_dir / f"{scheme}.png").replace(target)
        print(target)
    tmp_dir.rmdir()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
