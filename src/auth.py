import random
import time
from playwright.sync_api import sync_playwright, Page, Locator

from src.config import (
    LOGIN_URL,
    FPMARKETS_EMAIL,
    FPMARKETS_PASSWORD,
    FPMARKETS_PIN,
    HEADLESS,
    MIN_DELAY_MS,
    MAX_DELAY_MS,
    AUTH_STATE_PATH,
    SCREENSHOTS_DIR,
    validate_credentials,
    random_sleep,
    get_random_delay_ms,
)

from src.logger import log


def human_type(locator: Locator, text: str):
    """Types text character by character with randomized human-like delays."""
    locator.fill("")
    for char in text:
        locator.type(char, delay=random.randint(60, 180))
        # Occasional micro-pause between typing chunks (realistic human typing)
        if random.random() < 0.15:
            time.sleep(random.uniform(0.1, 0.25))


def perform_login(page: Page) -> bool:
    """Navigates to FP Markets login page and logs in with human-like interactions."""
    validate_credentials()

    log.info(f"Navigating to: {LOGIN_URL}")
    page.goto(LOGIN_URL, wait_until="domcontentloaded", timeout=60000)

    # Wait for the login form to load
    page.wait_for_selector("#loginform", timeout=15000)
    log.success("Login form loaded successfully.")

    # Random pause after page load
    random_sleep()

    # Fill email with human-like keystroke delays
    log.info("Entering email with human-like typing...")
    email_input = page.locator("#email")
    email_input.wait_for(state="visible", timeout=10000)
    human_type(email_input, FPMARKETS_EMAIL)

    # Random delay between filling email and password
    random_sleep()

    # Fill password with human-like keystroke delays
    log.info("Entering password with human-like typing...")
    password_input = page.locator("#password-field")
    password_input.wait_for(state="visible", timeout=10000)
    human_type(password_input, FPMARKETS_PASSWORD)

    # Random pause before clicking submit
    random_sleep()

    # Click Sign In button (Step 1)
    log.info("Submitting email & password...")
    check_login_btn = page.locator("#checklogin:visible, button#checklogin, button:visible:has-text('Sign in'), button:visible:has-text('SIGN IN')").first

    if check_login_btn.is_visible():
        check_login_btn.click()
    else:
        password_input.press("Enter")

    # Actively wait for the page to respond: either an error message or the PIN field.
    # (A fixed sleep here can fire before a slow error response renders, silently
    # skipping the failed-login branch below.)
    try:
        page.wait_for_selector("#show-error, #show-pin", state="visible", timeout=8000)
    except Exception:
        pass

    # Check for visible error message
    error_elem = page.locator("#show-error")
    if error_elem.is_visible() and error_elem.inner_text().strip():
        err_msg = error_elem.inner_text().strip()
        log.error(f"Login Failed: {err_msg}")
        page.screenshot(path=str(SCREENSHOTS_DIR / "login_error.png"))
        return False

    # Check if PIN input appears
    pin_input = page.locator("#show-pin input, input[placeholder*='PIN'], input[placeholder*='Pin'], input#pin-field, input[name='pin']").first
    pin_wrapper = page.locator("#show-pin")

    # Wait briefly to see if PIN section becomes visible
    try:
        if pin_wrapper.is_visible() or pin_input.is_visible():
            log.warning("PIN prompt detected!")
            if FPMARKETS_PIN:
                log.info("Entering PIN with human-like typing...")
                pin_input.wait_for(state="visible", timeout=5000)
                human_type(pin_input, FPMARKETS_PIN)

                random_sleep()

                log.info("Submitting PIN with #verifylogin button...")
                verify_login_btn = page.locator("#verifylogin:visible, button#verifylogin, button[type='submit']:visible, button:visible:has-text('Sign in')").first
                if verify_login_btn.is_visible():
                    verify_login_btn.click()
                else:
                    pin_input.press("Enter")
            else:
                log.warning("Please enter your PIN in the browser window (or set FPMARKETS_PIN in .env)...")
                # Wait for manual completion
                page.wait_for_url(lambda url: "portal.fpmarkets.com/login" not in url, timeout=60000)
    except Exception as e:
        log.debug(f"PIN check: {e}")

    # Wait for successful navigation away from login page
    try:
        page.wait_for_url(lambda url: "portal.fpmarkets.com/login" not in url, timeout=25000)
        log.success(f"✓ Login Successful! Current URL: {page.url}")

        # Take a confirmation screenshot
        page.screenshot(path=str(SCREENSHOTS_DIR / "dashboard_success.png"))
        return True
    except Exception:
        log.warning(f"Current URL after wait: {page.url}")
        page.screenshot(path=str(SCREENSHOTS_DIR / "login_state.png"))

        # If no longer on /login, consider it success
        if "/login" not in page.url:
            log.success("✓ Login Successful (redirected)!")
            return True
        else:
            log.error("Could not verify successful login. Check screenshots/login_state.png")
            return False


def get_authenticated_session(force_fresh_login: bool = False):
    """
    Launches a Playwright browser session with randomized timing and anti-bot arguments.
    If auth_state.json exists and force_fresh_login is False, reuses session cookies.
    Otherwise, performs a fresh login and saves state.
    """
    playwright = sync_playwright().start()

    # Browser launch arguments with anti-detection flags
    launch_args = [
        "--disable-blink-features=AutomationControlled",
        "--start-maximized",
        "--no-sandbox",
    ]

    try:
        browser = playwright.chromium.launch(headless=HEADLESS, args=launch_args)
    except Exception as e:
        if "Executable doesn't exist" in str(e) or "playwright install" in str(e):
            log.warning("Playwright Chromium browser binary not found. Downloading automatically...")
            import subprocess
            import sys
            subprocess.run([sys.executable, "-m", "playwright", "install", "chromium"], check=True)
            log.success("✓ Chromium browser installed successfully!")
            browser = playwright.chromium.launch(headless=HEADLESS, args=launch_args)
        else:
            raise e

    # Check if saved auth session exists
    if not force_fresh_login and AUTH_STATE_PATH.exists():
        log.info(f"Found existing session at {AUTH_STATE_PATH.name}. Reusing auth state...")
        context = browser.new_context(
            storage_state=str(AUTH_STATE_PATH),
            viewport={"width": 1920, "height": 1080},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        )
        page = context.new_page()
        page.goto("https://portal.fpmarkets.com/", wait_until="domcontentloaded")
        random_sleep(1500, 3000)

        # Check if session is still valid (not bounced back to login)
        if "/login" not in page.url:
            log.success(f"✓ Existing session is valid! URL: {page.url}")
            return playwright, browser, context, page
        else:
            log.warning("Saved session expired. Reusing browser window for fresh login...")
            AUTH_STATE_PATH.unlink(missing_ok=True)
            context.clear_cookies()
    else:
        context = browser.new_context(
            viewport={"width": 1920, "height": 1080},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        )
        page = context.new_page()

    login_success = perform_login(page)

    if login_success:
        # Save authenticated storage state
        context.storage_state(path=str(AUTH_STATE_PATH))
        log.success(f"✓ Authentication state saved to {AUTH_STATE_PATH.name}")
        return playwright, browser, context, page
    else:
        log.error("Login failed. Browser session will remain open for inspection for 10 seconds...")
        time.sleep(10)
        context.close()
        browser.close()
        playwright.stop()
        return None, None, None, None
