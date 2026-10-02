from rich.panel import Panel

from src.common.browser_session import close_browser_session
from src.common.config import RESTART_FROM_SCRATCH
from src.common.logger import log
from src.brokers.fpmarkets.auth import get_authenticated_session
from src.brokers.fpmarkets.config import (
    FPMARKETS_EMAIL,
    LEADER_URLS_CSV_PATH,
    TRADER_DETAILS_CSV_PATH,
    ensure_directories,
    validate_credentials,
)
from src.brokers.fpmarkets.orchestrator import (
    clear_debug_snapshots,
    is_leader_url_collection_complete,
    reset_all_data,
    scrape_all_leader_urls,
    scrape_all_trader_details,
)


def run(force_fresh_login: bool = False) -> None:
    """Entry point for `python main.py --broker fpmarkets`."""
    log.set_label("fpmarkets")
    ensure_directories()

    if RESTART_FROM_SCRATCH:
        log.warning("RESTART_FROM_SCRATCH is set - wiping previous run output before starting.")
        reset_all_data()

    clear_debug_snapshots()

    log.print(
        Panel.fit(
            "[bold cyan]FP Markets Portal - Playwright Scraper[/bold cyan]\n"
            f"[dim]Account:[/dim] [yellow]{FPMARKETS_EMAIL or '(Not configured in .env)'}[/yellow]",
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
        log.error("❌ Failed to authenticate with FP Markets.")
        raise SystemExit(1)

    try:
        log.success("🎉 Authentication successful!")

        if is_leader_url_collection_complete():
            log.info("Leader URL collection already complete (marker found); skipping to phase 2.")
        else:
            log.success("Collecting Copy Trading leader URLs...")
            total_urls_saved = scrape_all_leader_urls(page)

            log.print(
                Panel.fit(
                    f"[bold green]Leader URL Collection Complete![/bold green]\n"
                    f"[cyan]New URLs Saved:[/cyan] [yellow]{total_urls_saved}[/yellow]\n"
                    f"[cyan]Output CSV File:[/cyan] [green]{LEADER_URLS_CSV_PATH}[/green]",
                    border_style="green",
                )
            )

        log.success("Collecting per-trader profile details...")
        details_summary = scrape_all_trader_details(page)

        log.print(
            Panel.fit(
                f"[bold green]Trader Detail Scraping Complete![/bold green]\n"
                f"[cyan]New Profiles Saved:[/cyan] [yellow]{details_summary.new_saved:,}[/yellow]\n"
                f"[cyan]Total Profiles Scraped:[/cyan] [yellow]{details_summary.total_scraped:,}[/yellow]\n"
                f"[cyan]Remaining Profiles:[/cyan] [yellow]{details_summary.remaining:,}[/yellow]\n"
                f"[cyan]Output CSV File:[/cyan] [green]{TRADER_DETAILS_CSV_PATH}[/green]",
                border_style="green",
            )
        )

        log.info("Press Enter to close browser session...")
        input()
    finally:
        log.warning("Closing browser session...")
        close_browser_session(playwright, browser, context)
        log.success("✓ Closed.")
