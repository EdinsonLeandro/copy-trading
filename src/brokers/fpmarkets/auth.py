from playwright.sync_api import Page

from src.common.browser_session import get_authenticated_session as _get_authenticated_session, human_type
from src.common.config import HEADLESS, random_sleep
from src.common.logger import log
from src.brokers.fpmarkets.config import (
    AUTH_STATE_PATH,
    FPMARKETS_EMAIL,
    FPMARKETS_PASSWORD,
    FPMARKETS_PIN,
    HOME_URL,
    LOGIN_URL,
    SCREENSHOTS_DIR,
    validate_credentials,
)


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
    If a saved FP Markets session exists and force_fresh_login is False, reuses it.
    Otherwise, performs a fresh login and saves the new session state.
    """
    return _get_authenticated_session(
        auth_state_path=AUTH_STATE_PATH,
        home_url=HOME_URL,
        perform_login=perform_login,
        is_session_valid=lambda page: "/login" not in page.url,
        headless=HEADLESS,
        force_fresh_login=force_fresh_login,
    )
