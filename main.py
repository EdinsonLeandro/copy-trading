import sys
from rich.panel import Panel

from src.config import ensure_directories, validate_credentials, FPMARKETS_EMAIL, PROFILES_CSV_PATH
from src.auth import get_authenticated_session
from src.scraper import scrape_all_leader_profiles

from src.logger import log


def main():
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
        sys.exit(1)

    log.success("Starting authentication flow...")
    playwright, browser, context, page = get_authenticated_session(force_fresh_login=False)

    if not page:
        log.error("❌ Failed to authenticate with FP Markets.")
        sys.exit(1)

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


if __name__ == "__main__":
    main()

