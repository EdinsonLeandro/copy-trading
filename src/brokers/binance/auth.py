import time

from playwright.sync_api import Locator, Page

from src.common.browser_session import get_authenticated_session as _get_authenticated_session, human_type
from src.common.config import HEADLESS, random_sleep
from src.common.logger import log
from src.brokers.binance.config import (
    AUTH_STATE_PATH,
    BINANCE_EMAIL,
    BINANCE_PASSWORD,
    EMAIL_SUBMIT_WAIT_SECONDS,
    HOME_URL,
    LOGIN_URL,
    SCREENSHOTS_DIR,
    SECURITY_VERIFICATION_WAIT_SECONDS,
    validate_credentials,
)

_SUBMIT_BUTTON_SELECTOR = "button[data-e2e='btn-accounts-form-submit']"


def _type_and_verify(field: Locator, value: str, field_name: str, attempts: int = 3) -> None:
    """Clicks to focus, types, then verifies the field actually holds `value`.

    Binance's login inputs have been observed to drop the first 1-2 keystrokes
    when typed immediately after becoming visible (its React handlers likely
    aren't attached yet), so this focuses first, gives it a moment to settle,
    then re-types on mismatch instead of trusting a single blind pass.
    """
    for attempt in range(1, attempts + 1):
        field.click()
        random_sleep(200, 400)
        human_type(field, value)
        random_sleep(200, 400)
        if field.input_value() == value:
            return
        log.debug(f"{field_name} did not match after typing (attempt {attempt}/{attempts}); retrying...")
    log.warning(f"Could not reliably type {field_name} after {attempts} attempts; proceeding with last value.")


def perform_login(page: Page) -> bool:
    """Navigates to Binance's login page and logs in with human-like interactions.

    Binance's flow is a three-step wizard on accounts.binance.com: email, then
    password, then a "Security Verification" app-push prompt the account owner
    approves on their phone (there's no code to type here, so the script just
    pauses for SECURITY_VERIFICATION_WAIT_SECONDS), then an optional
    "Stay Logged In" dialog.
    """
    validate_credentials()

    log.info(f"Navigating to: {LOGIN_URL}")
    page.goto(LOGIN_URL, wait_until="domcontentloaded", timeout=60000)

    log.info("Entering email with human-like typing...")
    username_input = page.locator("input[name='username']")
    username_input.wait_for(state="visible", timeout=15000)
    random_sleep(300, 600)
    _type_and_verify(username_input, BINANCE_EMAIL, "email")

    random_sleep()

    log.info("Submitting email...")
    page.locator(_SUBMIT_BUTTON_SELECTOR).first.click()

    log.warning(
        f"Waiting {EMAIL_SUBMIT_WAIT_SECONDS}s in case a captcha appears "
        "(solve it manually if so)..."
    )
    time.sleep(EMAIL_SUBMIT_WAIT_SECONDS)

    log.info("Entering password with human-like typing...")
    password_input = page.locator("#password-input")
    password_input.wait_for(state="visible", timeout=15000)
    random_sleep(300, 600)
    _type_and_verify(password_input, BINANCE_PASSWORD, "password")

    random_sleep()

    log.info("Submitting password...")
    page.locator(_SUBMIT_BUTTON_SELECTOR).first.click()

    log.warning(
        f"Waiting {SECURITY_VERIFICATION_WAIT_SECONDS}s for manual Security Verification "
        "(approve the prompt on your Binance mobile app)..."
    )
    time.sleep(SECURITY_VERIFICATION_WAIT_SECONDS)

    try:
        stay_logged_in_btn = page.locator("button[aria-label='Yes']").first
        if stay_logged_in_btn.is_visible():
            log.info("Confirming 'Stay Logged In'...")
            stay_logged_in_btn.click()
    except Exception as e:
        log.debug(f"'Stay Logged In' prompt not shown: {e}")

    try:
        page.wait_for_url(lambda url: "/login" not in url, timeout=15000)
        log.success(f"✓ Login Successful! Current URL: {page.url}")
        page.screenshot(path=str(SCREENSHOTS_DIR / "dashboard_success.png"))
        return True
    except Exception:
        log.warning(f"Current URL after wait: {page.url}")
        page.screenshot(path=str(SCREENSHOTS_DIR / "login_state.png"))

        if "/login" not in page.url:
            log.success("✓ Login Successful (redirected)!")
            return True
        else:
            log.error("Could not verify successful login. Check screenshots/login_state.png")
            return False


def get_authenticated_session(force_fresh_login: bool = False):
    """
    Launches a Playwright browser session with randomized timing and anti-bot arguments.
    If a saved Binance session exists and force_fresh_login is False, reuses it.
    Otherwise, performs a fresh login (including the manual Security Verification
    pause) and saves the new session state.
    """
    return _get_authenticated_session(
        auth_state_path=AUTH_STATE_PATH,
        home_url=HOME_URL,
        perform_login=perform_login,
        is_session_valid=lambda page: "/login" not in page.url,
        headless=HEADLESS,
        force_fresh_login=force_fresh_login,
    )
