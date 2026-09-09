import re
import time
from typing import Any, Dict, List, Optional, Tuple

from playwright.sync_api import Frame, Page

from src.common.config import random_sleep
from src.common.logger import log
from src.common.playwright_utils import click_tab
from src.brokers.fpmarkets.config import COPY_TRADING_URL, SOCIAL_RATINGS_BASE_URL


def get_leaders_container(page: Page) -> Tuple[Any, Optional[Frame]]:
    """
    Finds the element or frame containing the Leaders trader cards and paginator.
    Ensures we target #tab2 / Leaders iframe rather than #tab1 (Overview).
    """
    # 1. Check if cards/paginator exist inside an embedded iframe
    for frame in page.frames:
        try:
            if frame.locator("section.ta-cards, .ta-card, mat-paginator").count() > 0:
                return frame, frame
        except Exception:
            continue

    # 2. Check within #tab2 container in the main page
    tab2 = page.locator("#tab2")
    if tab2.count() > 0:
        return tab2, None

    # 3. Fallback to main page
    return page, None


def activate_leaders_tab(page: Page):
    """
    Robustly activates the 'Leaders' tab by:
    1. Clicking the button using Playwright.
    2. Invoking the inline `openTab` JavaScript function.
    3. Setting display: block on #tab2 and hiding #tab1.
    4. Verifying the 'active' class on the tab button.
    """
    log.info("Activating 'Leaders' tab...")

    for attempt in range(3):
        # Native Playwright click with force=True
        leaders_btn = page.locator(
            "button[onclick*='tab2'], .tab-container button:has-text('Leaders'), button:has-text('Leaders')"
        ).first

        if leaders_btn.count() > 0:
            try:
                leaders_btn.scroll_into_view_if_needed()
                leaders_btn.click(force=True)
            except Exception:
                pass

        # Direct JS trigger to bypass Rocket Loader / event blockers
        page.evaluate("""
            () => {
                const btn = document.querySelector("button[onclick*='tab2']") ||
                            Array.from(document.querySelectorAll('.tab-container button')).find(b => b.textContent.trim().includes('Leaders'));
                if (btn) {
                    btn.click();
                    if (typeof openTab === 'function') {
                        try {
                            openTab({ currentTarget: btn, preventDefault: () => {} }, 'tab2');
                        } catch(e) {}
                    }
                    const tab2 = document.getElementById('tab2');
                    if (tab2) tab2.style.display = 'block';
                    const tab1 = document.getElementById('tab1');
                    if (tab1) tab1.style.display = 'none';
                    document.querySelectorAll('.tab-container button').forEach(b => b.classList.remove('active'));
                    btn.classList.add('active');
                }
            }
        """)

        random_sleep(1500, 2500)

        # Check if tab2 is visible or Leaders button has active class
        is_active = page.evaluate("""
            () => {
                const tab2 = document.getElementById('tab2');
                const isTabVisible = tab2 && window.getComputedStyle(tab2).display !== 'none';
                const btn = document.querySelector("button[onclick*='tab2']");
                const isBtnActive = btn && btn.classList.contains('active');
                return isTabVisible || isBtnActive;
            }
        """)

        if is_active:
            log.success("'Leaders' tab activated successfully.")
            return

    log.warning("Notice: Proceeding to wait for Leaders container...")


def navigate_to_leaders(page: Page) -> Any:
    """
    Navigates to the Copy Trading portal page, switches to Leaders tab,
    and waits for the full Leaders table & paginator to load.
    """
    log.info(f"Navigating to Copy Trading portal: {COPY_TRADING_URL}")
    page.goto(COPY_TRADING_URL, wait_until="domcontentloaded", timeout=60000)
    random_sleep(1500, 2500)

    # Wait for the tab container
    log.info("Locating tab bar...")
    page.wait_for_selector(".tab-container, button[onclick*='tab2'], button:has-text('Leaders')", timeout=20000)

    # Switch to Leaders tab
    activate_leaders_tab(page)

    # Wait for cards & paginator to load inside Leaders tab (#tab2 or frame)
    log.info("Waiting for Leaders cards and paginator to render...")
    for _ in range(25):
        target, frame = get_leaders_container(page)
        if target.locator(".ta-card, mat-paginator").count() > 0:
            log.success("Leaders table loaded.")
            return target
        time.sleep(1)

    # Final attempt
    target, _ = get_leaders_container(page)
    return target


def parse_page_info(container: Any) -> Tuple[int, int]:
    """
    Parses current page number and total pages from .mat-paginator-range-label.
    E.g. 'Page 1 of 105' -> (1, 105)
         '1 – 20 of 2100' -> (1, 105)
    """
    try:
        label_elem = container.locator(".mat-paginator-range-label").first
        if label_elem.count() > 0 and label_elem.is_visible():
            text = label_elem.inner_text().strip()

            # Format: "Page 1 of 105"
            page_match = re.search(r"Page\s+(\d+)\s+of\s+(\d+)", text, re.IGNORECASE)
            if page_match:
                return int(page_match.group(1)), int(page_match.group(2))

            # Format: "1 – 20 of 2100"
            range_match = re.search(r"(\d+)\s*[-–]\s*(\d+)\s+of\s+(\d+)", text, re.IGNORECASE)
            if range_match:
                start_idx = int(range_match.group(1))
                end_idx = int(range_match.group(2))
                total_items = int(range_match.group(3))
                per_page = max(1, end_idx - start_idx + 1)
                curr_page = (end_idx + per_page - 1) // per_page
                total_pages = (total_items + per_page - 1) // per_page
                return curr_page, total_pages
    except Exception as e:
        log.debug(f"Paginator label parse: {e}")

    return 1, 1


def extract_cards_from_page(container: Any, current_page: int) -> List[Dict[str, Any]]:
    """
    Extracts all trader basic identifiers (name, trader_id, profile_url) from current page cards.
    (Rank column is completely excluded).
    """
    cards = container.locator(".ta-card, div.ta-card--row")
    card_count = cards.count()
    extracted: List[Dict[str, Any]] = []

    for i in range(card_count):
        card = cards.nth(i)
        try:
            # Profile link element
            link_elem = card.locator(".ta-card__name a, a[href*='/widgets/ratings/'], a[href*='ratings']").first
            href = link_elem.get_attribute("href") or "" if link_elem.count() > 0 else ""

            # Extract trader ID
            trader_id = ""
            id_match = re.search(r"ratings/(\d+)", href)
            if id_match:
                trader_id = id_match.group(1)
            elif href:
                trader_id = href

            # Format absolute profile URL
            if trader_id and trader_id.isdigit():
                profile_url = f"{SOCIAL_RATINGS_BASE_URL}/widgets/ratings/{trader_id}?widgetKey=social_platform_ratings"
            elif href.startswith("http"):
                profile_url = href
            elif href.startswith("/"):
                profile_url = f"{SOCIAL_RATINGS_BASE_URL}{href}"
            else:
                profile_url = f"{SOCIAL_RATINGS_BASE_URL}/{href}" if href else ""

            # Extract Name
            name = ""
            name_elem = card.locator(".ta-card__name, span.mat-body-1").first
            if name_elem.count() > 0:
                name = name_elem.inner_text().strip()

            if profile_url or trader_id:
                extracted.append({
                    "name": name,
                    "trader_id": trader_id,
                    "profile_url": profile_url,
                    "page_number": current_page,
                })
        except Exception as e:
            log.debug(f"Error parsing card {i}: {e}")
            continue

    return extracted


def click_trading_tab(detail_page: Page) -> bool:
    """Switches a trader profile page to the 'Trading' tab."""
    return click_tab(
        detail_page,
        "Trading",
        "[transloco*='trading_sharpeRatio'], [transloco*='trading_absoluteGain']",
    )


def click_instruments_tab(detail_page: Page) -> bool:
    """Switches a trader profile page to the 'Instruments' tab."""
    return click_tab(
        detail_page,
        "Instruments",
        "[transloco*='instruments_bestTrade'], .apexcharts-legend-series",
    )
