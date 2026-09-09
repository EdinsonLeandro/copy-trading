CSV_HEADERS = [
    "name",
    "trader_id",
    "profile_url",
    "page_number",
    # Top Summary Header
    "return_total",
    "return_1d",
    "age_days",
    # Return/period Section
    "return_all_time",
    "return_year",
    "return_half_year",
    "return_quarter",
    "return_month",
    "return_week",
    "return_day",
    # Monthly Section
    "avg_return_weekly",
    "avg_return_monthly",
    "return_deviation",
    "return_deviation_monthly",
    "return_deviation_yearly",
    # Monthly bar chart (JSON object: {"Jan'26": "-34.87", ...})
    "monthly_chart",
    # Trading tab
    "trading_return_volatility_d",
    "trading_recovery_factor",
    "trading_absolute_gain",
    "trading_downside_deviation",
    "trading_sharpe_ratio",
    "trading_volatility_ratio",
    "trading_max_profit",
    "trading_max_drawdown",
    # Leverage bar chart (JSON array: [{"value": "0", "date": "2026-02-01"}, ...])
    "leverage_chart",
    # Instruments tab
    # Donut legend, trade count per symbol (JSON object: {"BTCUSD": "24", ...})
    "instruments",
    # Trade Statistics list (JSON object: {"Best trade": "$94.19", ...})
    "trade_statistics",
    # Metadata
    "scraped_at",
]

# Columns used to de-dupe traders already scraped in a previous run.
ID_FIELDS = ("trader_id", "profile_url")
