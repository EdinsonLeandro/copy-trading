from rich.panel import Panel

from src.common.logger import log
from src.brokers.binance.auth import get_authenticated_session
from src.brokers.binance.config import BINANCE_EMAIL, ensure_directories, validate_credentials


def run(force_fresh_login: bool = False) -> None:
    """Entry point for `python main.py --broker binance`."""
    log.set_label("binance")
    ensure_directories()

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
        log.warning(
            "Leaderboard scraping is not implemented yet. "
            "Session was established and saved for reuse."
        )

        log.info("Press Enter to close browser session...")
        input()
    finally:
        log.warning("Closing browser session...")
        context.close()
        browser.close()
        playwright.stop()
        log.success("✓ Closed.")
