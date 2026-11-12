import pytest

from src.brokers.binance.extractors import is_on_profile_page

PID = "5217253204810974721"


@pytest.mark.parametrize(
    "url, expected",
    [
        (f"https://www.binance.com/en/copy-trading/lead-details/{PID}?timeRange=365D", True),
        (f"https://www.binance.com/en/copy-trading/lead-details/{PID}/", True),
        # The redirect Binance does for unavailable portfolios.
        ("https://www.binance.com/en/copy-trading", False),
        # A different portfolio whose id starts with the same digits.
        (f"https://www.binance.com/en/copy-trading/lead-details/{PID}9", False),
        ("https://www.binance.com/en/copy-trading/lead-details/123", False),
    ],
)
def test_is_on_profile_page(url, expected):
    assert is_on_profile_page(url, PID) is expected


def test_is_on_profile_page_without_id_only_checks_page_type():
    assert is_on_profile_page("https://www.binance.com/en/copy-trading/lead-details/123", "")
    assert not is_on_profile_page("https://www.binance.com/en/copy-trading", "")
