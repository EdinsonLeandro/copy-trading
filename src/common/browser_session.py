import json
import random
import time
from pathlib import Path
from typing import Callable, Optional, Tuple

# Patchright is a drop-in fork of Playwright (same API) that patches the
# automation leaks Playwright itself can't hide from page scripts: the CDP
# `Runtime.enable` call fingerprinting scripts detect, and `page.evaluate`
# running in the page's own JS world (Patchright runs it in an isolated
# world by default, so the site's scripts can't observe our extraction JS).
from patchright.sync_api import BrowserContext, Locator, Page, Playwright, sync_playwright

from src.common.config import BROWSER_CHANNEL, HEADLESS, random_sleep
from src.common.logger import log

# No hardcoded user_agent is passed to the context below - the browser's
# default UA always matches the actual browser build across the main
# thread, Workers, and Client Hints (navigator.userAgentData). A pinned
# string goes stale over browser upgrades and creates exactly the kind of
# UA-vs-Client-Hints mismatch fingerprinting scripts (e.g. CreepJS) flag.


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

    `--start-maximized` alone is unreliable once combined with no fixed
    viewport, especially on Windows: the window can stay at its default
    launch size instead of adopting the full screen. CDP's
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


def launch_persistent_browser(
    playwright: Playwright,
    profile_dir: Path,
    headless: bool = HEADLESS,
) -> BrowserContext:
    """Launches the browser on a persistent on-disk profile (`profile_dir`).

    A persistent profile keeps IndexedDB, cache, service workers and history
    between runs, so the site sees the same returning device every time
    instead of a brand-new empty browser (which is what a fresh
    `new_context()` looks like, even with saved cookies loaded into it).

    Runs the installed Google Chrome by default (BROWSER_CHANNEL=chrome):
    the bundled Chromium build announces itself as "Chromium" without a
    "Google Chrome" brand in its Client Hints, which almost no real visitor
    sends.
    """
    profile_dir.mkdir(parents=True, exist_ok=True)
    launch_kwargs = dict(
        user_data_dir=str(profile_dir),
        channel=BROWSER_CHANNEL or None,
        headless=headless,
        no_viewport=True,
        args=[
            "--disable-blink-features=AutomationControlled",
            "--start-maximized",
        ],
        # `--enable-automation` shows the "controlled by automated test
        # software" bar and switches on automation-only browser behavior.
        ignore_default_args=["--enable-automation"],
    )
    try:
        return playwright.chromium.launch_persistent_context(**launch_kwargs)
    except Exception as e:
        if "Executable doesn't exist" not in str(e) and "install" not in str(e):
            raise
        if BROWSER_CHANNEL:
            log.error(
                f"Browser channel '{BROWSER_CHANNEL}' is not installed. Install Google Chrome, "
                "or set BROWSER_CHANNEL= (empty) in .env to use the bundled Chromium."
            )
            raise
        log.warning("Bundled Chromium binary not found. Downloading automatically...")
        import subprocess
        import sys
        subprocess.run([sys.executable, "-m", "patchright", "install", "chromium"], check=True)
        log.success("✓ Chromium browser installed successfully!")
        return playwright.chromium.launch_persistent_context(**launch_kwargs)


def _restore_missing_cookies(context: BrowserContext, auth_state_path: Path) -> None:
    """Adds back cookies from the last saved `auth_state_path` snapshot that
    the profile doesn't already have.

    Chrome drops session-only cookies (no expiry) when the browser closes,
    even on a persistent profile, and some portals keep the login in one of
    those. Only cookies missing from the profile are added, so fresher ones
    the profile already holds (e.g. rotated tokens) are never overwritten
    with stale copies.
    """
    if not auth_state_path.exists():
        return
    try:
        saved = json.loads(auth_state_path.read_text(encoding="utf-8")).get("cookies", [])
    except Exception as e:
        log.debug(f"Could not read saved session snapshot: {e}")
        return

    present = {(c["name"], c["domain"], c["path"]) for c in context.cookies()}
    missing = [c for c in saved if (c["name"], c["domain"], c["path"]) not in present]
    if missing:
        context.add_cookies(missing)
        log.debug(f"Restored {len(missing)} cookie(s) missing from the browser profile.")


def get_authenticated_session(
    profile_dir: Path,
    auth_state_path: Path,
    home_url: str,
    perform_login: Callable[[Page], bool],
    is_session_valid: Callable[[Page], bool],
    headless: bool = HEADLESS,
    force_fresh_login: bool = False,
) -> Tuple[Optional[Playwright], Optional[BrowserContext], Optional[Page]]:
    """
    Launches the browser on the persistent profile at `profile_dir` and
    returns a logged-in (playwright, context, page).

    If the profile was used before and force_fresh_login is False, reuses its
    session (validated via `is_session_valid`). Otherwise runs `perform_login`.
    After a valid session or successful login, a cookie snapshot is saved to
    `auth_state_path` (see _restore_missing_cookies for why).

    `perform_login` and `is_session_valid` are broker-specific: each site has its
    own login form/selectors and its own way of telling whether a session landed
    back on the login page.
    """
    # Checked before launching, since launching creates the directory.
    profile_was_used = profile_dir.exists() and any(profile_dir.iterdir())

    playwright = sync_playwright().start()
    try:
        context = launch_persistent_browser(playwright, profile_dir, headless)
    except Exception:
        playwright.stop()
        raise

    # A persistent context opens with one tab already; reuse it rather than
    # leaving a stray blank tab next to the one we drive.
    page = context.pages[0] if context.pages else context.new_page()
    maximize_window(page)

    if force_fresh_login:
        log.info("Fresh login requested; clearing the profile's cookies...")
        auth_state_path.unlink(missing_ok=True)
        context.clear_cookies()
    elif profile_was_used:
        log.info(f"Found existing browser profile at {profile_dir.name}. Reusing its session...")
        _restore_missing_cookies(context, auth_state_path)
        page.goto(home_url, wait_until="domcontentloaded")
        random_sleep(1500, 3000)

        if is_session_valid(page):
            log.success(f"✓ Existing session is valid! URL: {page.url}")
            context.storage_state(path=str(auth_state_path))
            return playwright, context, page

        log.warning("Saved session expired. Logging in again in the same browser profile...")
        auth_state_path.unlink(missing_ok=True)
        context.clear_cookies()

    try:
        login_success = perform_login(page)
    except Exception:
        log.error("perform_login raised an exception. Closing browser session...")
        close_browser_session(playwright, context)
        raise

    if login_success:
        auth_state_path.parent.mkdir(parents=True, exist_ok=True)
        context.storage_state(path=str(auth_state_path))
        log.success(f"✓ Logged in; session kept in browser profile {profile_dir.name}")
        return playwright, context, page

    log.error("Login failed. Browser session will remain open for inspection for 10 seconds...")
    time.sleep(10)
    close_browser_session(playwright, context)
    return None, None, None


def close_browser_session(
    playwright: Optional[Playwright],
    context: Optional[BrowserContext],
) -> None:
    """
    Tears down a session from get_authenticated_session, closing each piece
    independently so one failing step (e.g. a context left wedged by a page
    that stopped responding) doesn't skip the rest or mask the original
    error that triggered the shutdown. Closing a persistent context also
    closes the browser and flushes the profile to disk.
    """
    for name, closer in (
        ("context", context.close if context else None),
        ("playwright", playwright.stop if playwright else None),
    ):
        if closer is None:
            continue
        try:
            closer()
        except Exception as e:
            log.warning(f"Error while closing {name}: {e}")
