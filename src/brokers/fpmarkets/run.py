from rich.panel import Panel

from src.common.logger import log
from src.brokers.fpmarkets.auth import get_authenticated_session
from src.brokers.fpmarkets.config import FPMARKETS_EMAIL, PROFILES_CSV_PATH, ensure_directories, validate_credentials
from src.brokers.fpmarkets.orchestrator import scrape_all_leader_profiles


def run(force_fresh_login: bool = False) -> None:
    """Entry point for `python main.py --broker fpmarkets`."""
    log.set_label("fpmarkets")
    ensure_directories()

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
        log.success("🎉 Authentication successful! Launching Copy Trading Scraper...")

        total_scraped = scrape_all_leader_profiles(page)

        log.print(
            Panel.fit(
                f"[bold green]Scraping Completed Successfully![/bold green]\n"
                f"[cyan]Total Profiles Processed:[/cyan] [yellow]{total_scraped}[/yellow]\n"
                f"[cyan]Output CSV File:[/cyan] [green]{PROFILES_CSV_PATH}[/green]",
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
