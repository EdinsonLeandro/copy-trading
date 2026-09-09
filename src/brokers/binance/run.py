from src.common.logger import log


def run(force_fresh_login: bool = False) -> None:
    """Entry point for `python main.py --broker binance`.

    Not implemented yet. Follow the fpmarkets package's shape when building this out:
    config.py (credentials/URLs/paths), auth.py (perform_login + get_authenticated_session,
    built on src.common.browser_session), csv_schema.py (this broker's own CSV_HEADERS/ID_FIELDS),
    navigation.py, extractors.py, orchestrator.py.
    """
    log.error(
        "Binance scraper is not implemented yet. "
        "See src/brokers/fpmarkets/ for the reference implementation to follow."
    )
    raise SystemExit(1)
