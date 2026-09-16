import random
import time
from pathlib import Path
from typing import Callable, Optional, Tuple

from playwright.sync_api import Browser, BrowserContext, Locator, Page, Playwright, sync_playwright

from src.common.config import HEADLESS, random_sleep
from src.common.logger import log

DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)

def human_type(locator: Locator, text: str) -> None:
    """Types text character by character with randomized human-like delays."""
    locator.fill("")
    for char in text:
        locator.type(char, delay=random.randint(60, 180))
        # Occasional micro-pause between typing chunks (realistic human typing)
        if random.random() < 0.15:
            time.sleep(random.uniform(0.1, 0.25))


def maximize_window(page: Page) -> None:
    """Force-maximizes the OS browser window via CDP.

    `--start-maximized` alone is unreliable once combined with `viewport=None` +
    a freshly-opened `new_page()`: the window can stay at its default launch size
    instead of adopting the full screen, especially on Windows. CDP's
    `Browser.setWindowBounds` is the reliable way to force it.
    """
    try:
        cdp = page.context.new_cdp_session(page)
        window_info = cdp.send("Browser.getWindowForTarget")
        cdp.send(
            "Browser.setWindowBounds",
            {"windowId": window_info["windowId"], "bounds": {"windowState": "maximized"}},
        )
    except Exception as e:
        log.debug(f"Could not force-maximize browser window: {e}")


def launch_browser(playwright: Playwright, headless: bool = HEADLESS) -> Browser:
    """Launches Chromium with anti-detection flags, auto-installing the binary if missing."""
    launch_args = [
        "--disable-blink-features=AutomationControlled",
        "--start-maximized",
        "--no-sandbox",
    ]
    try:
        return playwright.chromium.launch(headless=headless, args=launch_args)
    except Exception as e:
        if "Executable doesn't exist" in str(e) or "playwright install" in str(e):
            log.warning("Playwright Chromium browser binary not found. Downloading automatically...")
            import subprocess
            import sys
            subprocess.run([sys.executable, "-m", "playwright", "install", "chromium"], check=True)
            log.success("✓ Chromium browser installed successfully!")
            return playwright.chromium.launch(headless=headless, args=launch_args)
        raise


def get_authenticated_session(
    auth_state_path: Path,
    home_url: str,
    perform_login: Callable[[Page], bool],
    is_session_valid: Callable[[Page], bool],
    headless: bool = HEADLESS,
    force_fresh_login: bool = False,
) -> Tuple[Optional[Playwright], Optional[Browser], Optional[BrowserContext], Optional[Page]]:
    """
    Launches a Playwright browser session with randomized timing and anti-bot arguments.
    If `auth_state_path` exists and force_fresh_login is False, reuses saved session
    cookies (validated via `is_session_valid`). Otherwise runs `perform_login` and
    saves the resulting state to `auth_state_path`.

    `perform_login` and `is_session_valid` are broker-specific: each site has its
    own login form/selectors and its own way of telling whether a session landed
    back on the login page.
    """
    playwright = sync_playwright().start()
    browser = launch_browser(playwright, headless)

    if not force_fresh_login and auth_state_path.exists():
        log.info(f"Found existing session at {auth_state_path.name}. Reusing auth state...")
        context = browser.new_context(
            storage_state=str(auth_state_path),
            viewport=None,
            user_agent=DEFAULT_USER_AGENT,
        )
        page = context.new_page()
        maximize_window(page)
        page.goto(home_url, wait_until="domcontentloaded")
        random_sleep(1500, 3000)

        if is_session_valid(page):
            log.success(f"✓ Existing session is valid! URL: {page.url}")
            return playwright, browser, context, page
        else:
            log.warning("Saved session expired. Reusing browser window for fresh login...")
            auth_state_path.unlink(missing_ok=True)
            context.clear_cookies()
    else:
        context = browser.new_context(viewport=None, user_agent=DEFAULT_USER_AGENT)
        page = context.new_page()
        maximize_window(page)

    try:
        login_success = perform_login(page)
    except Exception:
        log.error("perform_login raised an exception. Closing browser session...")
        context.close()
        browser.close()
        playwright.stop()
        raise

    if login_success:
        auth_state_path.parent.mkdir(parents=True, exist_ok=True)
        context.storage_state(path=str(auth_state_path))
        log.success(f"✓ Authentication state saved to {auth_state_path.name}")
        return playwright, browser, context, page
    else:
        log.error("Login failed. Browser session will remain open for inspection for 10 seconds...")
        time.sleep(10)
        context.close()
        browser.close()
        playwright.stop()
        return None, None, None, None
