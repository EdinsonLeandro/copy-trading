"""
Standalone anti-detection sanity check, broker-agnostic.

Launches the exact same browser/context configuration every broker session
in this repo uses (see src/common/browser_session.py), points it at two
public fingerprint-check sites instead of a real broker, and saves
screenshots + a few key raw navigator/Client-Hints values so what the
current Playwright setup exposes can be reviewed before/after any
anti-detection change.

Not part of the resumable production pipeline - a dev-only diagnostic.
See scripts/fingerprint_check/fingerprint_check_findings.txt for the last
recorded findings.

Usage:
    python scripts/fingerprint_check/fingerprint_check.py
"""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from playwright.sync_api import sync_playwright  # noqa: E402

from src.common.browser_session import launch_browser  # noqa: E402
from src.common.logger import log  # noqa: E402

OUT_DIR = Path(__file__).resolve().parent / "fingerprint_check_results"


def main() -> None:
    OUT_DIR.mkdir(exist_ok=True)

    playwright = sync_playwright().start()
    browser = launch_browser(playwright, headless=False)
    context = browser.new_context(viewport=None)
    page = context.new_page()

    try:
        log.info("Checking bot.sannysoft.com ...")
        page.goto("https://bot.sannysoft.com", wait_until="networkidle", timeout=30000)
        page.wait_for_timeout(2000)
        page.screenshot(path=str(OUT_DIR / "sannysoft.png"), full_page=True)
        log.success(f"Saved {OUT_DIR / 'sannysoft.png'}")

        log.info("Checking abrahamjuliot.github.io/creepjs ...")
        page.goto("https://abrahamjuliot.github.io/creepjs/", wait_until="networkidle", timeout=45000)
        # CreepJS runs its fingerprinting async after load; give it time to settle.
        page.wait_for_timeout(8000)
        page.screenshot(path=str(OUT_DIR / "creepjs.png"), full_page=True)
        log.success(f"Saved {OUT_DIR / 'creepjs.png'}")

        # A few key raw values directly, in case the screenshots are hard to
        # read - the ones worth eyeballing first are webdriver and any
        # userAgent-vs-userAgentData version mismatch.
        raw = page.evaluate(
            """
            () => ({
                webdriver: navigator.webdriver,
                userAgent: navigator.userAgent,
                userAgentDataBrands: navigator.userAgentData
                    ? navigator.userAgentData.brands
                    : "unsupported",
                languages: navigator.languages,
                pluginsLength: navigator.plugins.length,
                hasChromeRuntime: !!(window.chrome && window.chrome.runtime),
                permissionsQueryExists: !!(navigator.permissions && navigator.permissions.query),
            })
            """
        )
        log.info(f"Raw navigator values: {raw}")

    finally:
        time.sleep(2)
        context.close()
        browser.close()
        playwright.stop()


if __name__ == "__main__":
    main()
