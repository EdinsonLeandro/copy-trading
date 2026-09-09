import argparse

from src.brokers.binance.run import run as run_binance
from src.brokers.fpmarkets.run import run as run_fpmarkets

BROKER_RUNNERS = {
    "fpmarkets": run_fpmarkets,
    "binance": run_binance,
}


def main() -> None:
    parser = argparse.ArgumentParser(description="Copy Trading leaderboard scraper")
    parser.add_argument(
        "--broker",
        required=True,
        choices=sorted(BROKER_RUNNERS),
        help="Which broker's copy-trading leaderboard to scrape",
    )
    parser.add_argument(
        "--force-fresh-login",
        action="store_true",
        help="Ignore any saved session and log in again",
    )
    args = parser.parse_args()

    BROKER_RUNNERS[args.broker](force_fresh_login=args.force_fresh_login)


if __name__ == "__main__":
    main()
