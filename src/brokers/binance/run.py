from rich.panel import Panel

from src.common.config import RESTART_FROM_SCRATCH
from src.common.logger import log
from src.brokers.binance.auth import get_authenticated_session
from src.brokers.binance.config import (
    BINANCE_EMAIL,
    PORTFOLIO_URLS_CSV_PATH,
    TRADER_DETAILS_CSV_PATH,
    ensure_directories,
    validate_credentials,
)
from src.brokers.binance.orchestrator import (
    clear_debug_snapshots,
    is_portfolio_url_collection_complete,
    reset_all_data,
    scrape_all_portfolio_urls,
    scrape_all_trader_details,
)


def run(force_fresh_login: bool = False) -> None:
    """Entry point for `python main.py --broker binance`."""
    log.set_label("binance")
    ensure_directories()

    if RESTART_FROM_SCRATCH:
        log.warning("RESTART_FROM_SCRATCH is set - wiping previous run output before starting.")
        reset_all_data()

    clear_debug_snapshots()

    log.print(
        Panel.fit(
            "[bold cyan]Binance Portal - Playwright Scraper[/bold cyan]\n"
            f"[dim]Account:[/dim] [yellow]{BINANCE_EMAIL or '(Not configured in .env)'}[/yellow]",
            border_style="cyan",
        )
    )

    try:
        validate_credentials()
    except ValueError as e:
        log.error(f"Configuration Error: {e}")
        log.warning("Please edit the .env file with your valid credentials and rerun this script.")
        raise SystemExit(1)

    log.success("Starting authentication flow...")
    playwright, browser, context, page = get_authenticated_session(force_fresh_login=force_fresh_login)

    if not page:
        log.error("❌ Failed to authenticate with Binance.")
        raise SystemExit(1)

    try:
        log.success("🎉 Authentication successful!")

        if is_portfolio_url_collection_complete():
            log.info("Portfolio URL collection already complete (marker found); skipping to phase 2.")
        else:
            log.success("Collecting Copy Trading portfolio URLs...")
            total_urls_saved = scrape_all_portfolio_urls(page)

            log.print(
                Panel.fit(
                    f"[bold green]Portfolio URL Collection Complete![/bold green]\n"
                    f"[cyan]New URLs Saved:[/cyan] [yellow]{total_urls_saved}[/yellow]\n"
                    f"[cyan]Output CSV File:[/cyan] [green]{PORTFOLIO_URLS_CSV_PATH}[/green]",
                    border_style="green",
                )
            )

        log.success("Collecting per-trader profile details...")
        total_details_saved = scrape_all_trader_details(page)

        log.print(
            Panel.fit(
                f"[bold green]Trader Detail Scraping Complete![/bold green]\n"
                f"[cyan]New Profiles Saved:[/cyan] [yellow]{total_details_saved}[/yellow]\n"
                f"[cyan]Output CSV File:[/cyan] [green]{TRADER_DETAILS_CSV_PATH}[/green]",
                border_style="green",
            )
        )

        log.info("Press Enter to close browser session...")
        input()
    finally:
        log.warning("Closing browser session...")
        context.close()
        browser.close()
        playwright.stop()
        log.success("✓ Closed.")
