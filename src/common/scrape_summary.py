from typing import NamedTuple


class TraderDetailsSummary(NamedTuple):
    """Outcome of a broker's phase-2 (trader detail) run, for the end-of-run panel."""
    new_saved: int  # profiles saved during this run
    total_scraped: int  # profiles from the phase-1 URL list scraped so far (all runs)
    remaining: int  # profiles from the phase-1 URL list still left to scrape
