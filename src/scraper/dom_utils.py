from typing import Any, Callable, Optional

from playwright.sync_api import Page

from src.config import random_sleep
from src.logger import log


def evaluate_with_frame_fallback(
    page: Page,
    js: str,
    is_sufficient: Optional[Callable[[Any], bool]] = None,
) -> Any:
    """
    Runs `js` on the main page first; if the result isn't good enough, retries
    it against each child frame and returns the first sufficient result.

    `is_sufficient` defaults to "truthy". Falls back to the main-page result
    (even if insufficient) when no frame produces a better one.
    """
    is_sufficient = is_sufficient or (lambda r: bool(r))

    result = page.evaluate(js)
    if is_sufficient(result):
        return result

    for frame in page.frames:
        try:
            frame_result = frame.evaluate(js)
        except Exception:
            continue
        if is_sufficient(frame_result):
            return frame_result

    return result


def wait_for_evaluate(
    page: Page,
    js: str,
    is_sufficient: Callable[[Any], bool],
    attempts: int = 10,
    interval_ms: int = 500,
) -> Any:
    """
    Polls `evaluate_with_frame_fallback(page, js, is_sufficient)` up to `attempts`
    times, sleeping `interval_ms` between tries, until `is_sufficient` passes.

    A DOM wrapper (e.g. the tab body) can exist well before Angular finishes
    binding data into it, so checking for the wrapper's presence with
    `wait_for_selector` is not proof the values inside are populated yet. This
    instead re-checks the actual extracted values, the same way the Leaders
    container polls for its cards (see `navigate_to_leaders`).

    Returns the last (possibly insufficient) result if it never passes.
    """
    result: Any = None
    for attempt in range(attempts):
        result = evaluate_with_frame_fallback(page, js, is_sufficient)
        if is_sufficient(result):
            return result
        if attempt < attempts - 1:
            page.wait_for_timeout(interval_ms)
    return result


def click_tab(detail_page: Page, tab_name: str, wait_selector: str) -> bool:
    """
    Switches a trader profile page (Angular Material tabs) to the tab labeled
    `tab_name`, using a human-like scroll/click/delay pattern to avoid bot
    detection, then waits for `wait_selector` to confirm the tab rendered.
    """
    try:
        tab_btn = detail_page.locator(f"div[role='tab']:has-text('{tab_name}')").first
        if tab_btn.count() == 0:
            return False

        tab_btn.scroll_into_view_if_needed()
        random_sleep(400, 900)
        tab_btn.click(force=True)
        random_sleep(1200, 2200)

        detail_page.wait_for_selector(wait_selector, timeout=10000)
        return True
    except Exception as e:
        log.debug(f"{tab_name} tab click: {e}")
        return False
