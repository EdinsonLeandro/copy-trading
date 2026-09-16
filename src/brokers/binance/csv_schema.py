PORTFOLIO_URLS_CSV_HEADERS = [
    "portfolio_id",
    "profile_url",
    "page_number",
    "scraped_at",
]

# Columns used to de-dupe portfolios already discovered in a previous run.
PORTFOLIO_URLS_ID_FIELDS = ("portfolio_id", "profile_url")

# Phase 2 output: per-trader profile details, keyed off the URLs collected
# into PORTFOLIO_URLS_CSV_PATH.
TRADER_DETAILS_CSV_HEADERS = [
    "portfolio_id",
    "profile_url",
    "name",
    "level",
    "description",
    "leverage",
    "tradfi",
    "api_trading",
    # JSON array string of the remaining achievement tags, e.g.
    # ["Top Performer", "Money Maker", "Most Resilient", "Whale Manager",
    # "Solid Growth", "Low Leverage"]
    "tags",
    "days_trading",
    "copiers",
    "total_copiers",
    "mock_copiers",
    "closed_portfolios",
    "mock_copy_available",
    "roi",
    "pnl",
    "copier_pnl",
    "sharpe_ratio",
    "mdd",
    "win_rate",
    "win_positions",
    "total_positions",
    # Lead Trader Overview panel
    "aum",
    "profit_sharing",
    "leading_margin_balance",
    "lock_up_period",
    "minimum_copy_amount",
    # Asset Preferences donut legend (JSON object: {"ZEC": "54.08%", "BNB": "12.43%", ...})
    "asset_preferences",
    # ROI time series (JSON array: [{"date": "2026-09-16", "value": 0}, ...]),
    # captured via network response interception on the ROI chart's own
    # chart-data XHR rather than parsed from the rendered SVG.
    "roi_chart",
    # Every closed position row (JSON array of {"symbol", "tags", "status",
    # "fields"}), e.g. [{"symbol": "ETHUSDT", "tags": ["Perp", "6X", "Cross
    # Long"], "status": "Closed", "fields": {"Opened": "2026-09-14 04:07:53",
    # "Entry Price": "2,520.77 USDT", "Max. Open Interest": "357.027 ETH",
    # "Closing PNL": "-11,725.91 USDT", "Closed": "2026-09-14 09:08:40",
    # "Avg. Close Price": "2,488.99 USDT", "Closed Vol.": "357.027 ETH"}}].
    # "fields" is a generic label->value map rather than fixed columns,
    # since different position types are expected to show different fields.
    "position_history",
    # True when the portfolio hides its trading history entirely (Binance's
    # own "this is a 'private' portfolio" empty state) - lets an empty
    # position_history be told apart from a trader with genuinely zero
    # closed positions.
    "is_private_portfolio",
    # Every "Copy Traders" row across all pages (JSON array), e.g.
    # [{"User ID": "Tan***ian", "Copy Margin Balance": "64.74 USDT",
    # "Total PNL": "+5.89 USDT", "Total ROI": "+9.81%", "Duration": "27
    # Days"}, ...]. Keys come from the table's own headers rather than a
    # fixed schema.
    "copy_traders",
    "scraped_at",
]

# Columns used to de-dupe traders already scraped in a previous run.
TRADER_DETAILS_ID_FIELDS = ("portfolio_id", "profile_url")
