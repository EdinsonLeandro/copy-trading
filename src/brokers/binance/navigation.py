import re
from typing import Any, Dict, List, Optional, Tuple

from playwright.sync_api import Page

from src.common.config import random_sleep
from src.common.logger import log
from src.common.playwright_utils import click_tab
from src.brokers.binance.config import COPY_TRADING_URL, PORTFOLIO_BASE_URL

_CARD_LINK_SELECTOR = "a.bn-balink[href*='/copy-trading/lead-details/']"
# Binance reuses `id="bn-tab-1"` across unrelated tab bars on this page (e.g. a
# "Spot"/"Futures" asset-type tablist shares the id with this one), so this
# selects by the tab's visible text instead of its (non-unique) id.
_ALL_PORTFOLIOS_TAB_SELECTOR = "div[role='tab']:has-text('All Portfolios')"
_TIME_RANGE_FIELD_SELECTOR = "div.bn-select-field:has-text('Days')"
_TIME_RANGE_OPTION_SELECTOR = "div.bn-select-option"
_SMART_FILTER_CHECKBOX_SELECTOR = "div.bn-checkbox:has-text('Smart Filter')"
_NEXT_BUTTON_SELECTOR = "div.bn-pagination-next"
_PAGINATION_ITEM_SELECTOR = "a.bn-pagination-item"


def _wait_for_cards(page: Page, timeout: int = 20000) -> None:
    page.wait_for_selector(_CARD_LINK_SELECTOR, timeout=timeout)


def navigate_to_copy_trading(page: Page) -> None:
    """Navigates to the Copy Trading leaderboard and waits for it to render."""
    log.info(f"Navigating to Copy Trading portal: {COPY_TRADING_URL}")
    page.goto(COPY_TRADING_URL, wait_until="domcontentloaded", timeout=60000)
    random_sleep(1500, 2500)
    _wait_for_cards(page)
    log.success("Copy Trading leaderboard loaded.")


def select_all_portfolios_tab(page: Page, attempts: int = 3) -> None:
    """Clicks the 'All Portfolios' tab and confirms it becomes selected."""
    tab = page.locator(_ALL_PORTFOLIOS_TAB_SELECTOR).first

    for attempt in range(1, attempts + 1):
        tab.scroll_into_view_if_needed()
        tab.click()
        random_sleep(500, 1000)

        if tab.get_attribute("aria-selected") == "true":
            log.success("'All Portfolios' tab selected.")
            return

        log.debug(f"'All Portfolios' tab not selected yet (attempt {attempt}/{attempts}); retrying...")

    log.warning("Could not confirm 'All Portfolios' tab selection; proceeding anyway.")


def select_time_range(page: Page, label: str = "365 Days", attempts: int = 3) -> None:
    """Opens the time-range dropdown and selects the option matching `label` exactly."""
    field = page.locator(_TIME_RANGE_FIELD_SELECTOR).first

    for attempt in range(1, attempts + 1):
        field.scroll_into_view_if_needed()
        field.click()
        random_sleep(400, 800)

        options = page.locator(_TIME_RANGE_OPTION_SELECTOR)
        target: Optional[Any] = None
        for i in range(options.count()):
            option = options.nth(i)
            if option.inner_text().strip() == label:
                target = option
                break

        if target is None:
            log.debug(f"Time range option '{label}' not found (attempt {attempt}/{attempts}); retrying...")
            continue

        target.click()
        random_sleep(500, 1000)

        if label in (field.inner_text() or ""):
            log.success(f"Time range set to '{label}'.")
            return

        log.debug(f"Time range did not update to '{label}' (attempt {attempt}/{attempts}); retrying...")

    log.warning(f"Could not confirm time range was set to '{label}'; proceeding anyway.")


def disable_smart_filter(page: Page, attempts: int = 3) -> None:
    """Unchecks the 'Smart Filter' checkbox if it is currently checked, then
    waits for the leaderboard to reload with the new filter applied."""
    checkbox = page.locator(_SMART_FILTER_CHECKBOX_SELECTOR).first

    if checkbox.get_attribute("aria-checked") != "true":
        log.debug("Smart Filter already disabled.")
        return

    for attempt in range(1, attempts + 1):
        checkbox.scroll_into_view_if_needed()
        checkbox.click()
        random_sleep(500, 1000)

        if checkbox.get_attribute("aria-checked") == "false":
            log.success("Smart Filter disabled.")
            break

        log.debug(f"Smart Filter still checked (attempt {attempt}/{attempts}); retrying...")
    else:
        log.warning("Could not confirm Smart Filter was disabled; proceeding anyway.")

    # Wait for the leaderboard to finish reloading with the filter change applied.
    random_sleep(1500, 2500)
    _wait_for_cards(page)


def extract_portfolio_cards(page: Page, page_number: int) -> List[Dict[str, Any]]:
    """Extracts portfolio_id/profile_url for every trader card on the current page."""
    links = page.locator(_CARD_LINK_SELECTOR)
    count = links.count()
    extracted: List[Dict[str, Any]] = []

    for i in range(count):
        link = links.nth(i)
        try:
            href = link.get_attribute("href") or ""
            if not href:
                continue

            id_match = re.search(r"lead-details/(\d+)", href)
            portfolio_id = id_match.group(1) if id_match else ""

            profile_url = href if href.startswith("http") else f"{PORTFOLIO_BASE_URL}{href}"

            if portfolio_id or profile_url:
                extracted.append({
                    "portfolio_id": portfolio_id,
                    "profile_url": profile_url,
                    "page_number": page_number,
                })
        except Exception as e:
            log.debug(f"Error parsing portfolio card {i}: {e}")
            continue

    return extracted


def parse_pagination_info(page: Page) -> Tuple[int, int]:
    """Parses (current_page, total_pages) from the pagination bar.
    Returns (0, 0) if it cannot be determined."""
    try:
        items = page.locator(_PAGINATION_ITEM_SELECTOR)
        count = items.count()
        if count == 0:
            return 0, 0

        current_page = 0
        total_pages = 0
        for i in range(count):
            item = items.nth(i)
            text = item.inner_text().strip()
            if not text.isdigit():
                continue
            total_pages = max(total_pages, int(text))
            if "active" in (item.get_attribute("class") or ""):
                current_page = int(text)

        return current_page, total_pages
    except Exception as e:
        log.debug(f"Pagination parse: {e}")
        return 0, 0


def is_next_button_disabled(page: Page) -> bool:
    next_button = page.locator(_NEXT_BUTTON_SELECTOR).first
    if next_button.count() == 0:
        return True

    return (
        next_button.get_attribute("aria-disabled") == "true"
        or "disabled" in (next_button.get_attribute("class") or "").split()
    )


def click_next_page(page: Page) -> None:
    """Clicks the pagination Next button and waits for the page to advance."""
    curr_page, _ = parse_pagination_info(page)

    next_button = page.locator(_NEXT_BUTTON_SELECTOR).first
    next_button.scroll_into_view_if_needed()
    next_button.click()

    # Human-like pause before reacting to the new page, on top of the
    # transition-detection polling below.
    random_sleep(1000, 2500)

    for _ in range(20):
        random_sleep(300, 500)
        new_curr_page, _ = parse_pagination_info(page)
        if new_curr_page != curr_page and new_curr_page > 0:
            break
    else:
        random_sleep(1500, 2500)

    _wait_for_cards(page)


def click_position_history_tab(detail_page: Page) -> bool:
    """Switches a trader profile page to the 'Position History' tab.
    Confirmed via manual DevTools inspection that this table renders every
    row into the DOM upfront (no virtualization/windowing), so a plain
    query after this returns True is enough - no scroll-and-accumulate loop
    is needed to reach rows further down the table."""
    return click_tab(detail_page, "Position History", "tr.bn-web-table-row")
