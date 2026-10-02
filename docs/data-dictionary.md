# Data Dictionary

What each CSV column written to `data/<broker>/` means, where on the site it comes from, and how to parse it.

## General rules (all brokers)

- **Values are stored exactly as displayed on the site**, as text: `"+9.81%"`, `"64.74 USDT"`, `"$94.19"`, `"1,234"`. Nothing is converted to numbers at scrape time, so strip signs, `%`, currency suffixes and thousands separators during analysis.
- **Empty string** means the field wasn't found on the page (not rendered, hidden, or the site changed). It does not mean zero.
- **JSON columns** hold a JSON string (`json.loads` / `pd.json_normalize`). An empty object/array (`{}` / `[]`) means the section rendered with no entries.
- **Booleans** are written as `True` / `False`.
- **`scraped_at`** is the UTC time the row was written, `YYYY-MM-DD HH:MM:SS`.
- **`page_number`** is the leaderboard page the trader was found on during Phase 1. Rankings shift between runs, so treat it as approximate.
- **Deduplication:** a trader is only scraped once. Re-running never updates an existing row; to refresh data, set `RESTART_FROM_SCRATCH=True`.

Column lists are defined in `src/brokers/<broker>/csv_schema.py`, which is the source of truth if this document falls behind.

---

## FP Markets

### `data/fpmarkets/leader_urls.csv` (Phase 1)

| Column | Description |
|---|---|
| `name` | Leader's display name from the leaderboard card (the profile page doesn't show it). |
| `trader_id` | Numeric ID from the profile link (`/widgets/ratings/<id>`). Unique key. |
| `profile_url` | Full profile URL on `socialratings.fpglobaltrading.com`. Unique key. |
| `page_number` | Leaderboard page where the card was found. |
| `scraped_at` | UTC timestamp. |

### `data/fpmarkets/trader_details.csv` (Phase 2)

`name`, `trader_id`, `profile_url` and `page_number` are copied from the Phase 1 row.

**Return tab: top summary**

| Column | Site label |
|---|---|
| `return_total` | Return (total) |
| `return_1d` | Return (1D) |
| `age_days` | Age (Days): days since the account started trading. |

**Return tab: Return/period**

| Column | Site label |
|---|---|
| `return_all_time` | All time |
| `return_year` | Year |
| `return_half_year` | Half year |
| `return_quarter` | Quarter |
| `return_month` | Month |
| `return_week` | Week |
| `return_day` | Day |

**Return tab: Monthly section**

| Column | Site label |
|---|---|
| `avg_return_weekly` | Average return (Weekly) |
| `avg_return_monthly` | Average return (Monthly) |
| `return_deviation` | Return deviation |
| `return_deviation_monthly` | Return deviation (Monthly) |
| `return_deviation_yearly` | Return deviation (Yearly) |
| `monthly_chart` | JSON object, month label → return for that month, from the monthly bar chart. Example: `{"Jan'26": "-34.87", "Feb'26": "12.10"}`. Values are the chart's raw numbers (no `%`). |

**Trading tab**

| Column | Site label |
|---|---|
| `trading_return_volatility_d` | Return volatility (D) |
| `trading_recovery_factor` | Recovery factor |
| `trading_absolute_gain` | Absolute gain |
| `trading_downside_deviation` | Downside deviation |
| `trading_sharpe_ratio` | Sharpe ratio |
| `trading_volatility_ratio` | Volatility ratio |
| `trading_max_profit` | Max profit (from the "Info" side list) |
| `trading_max_drawdown` | Max drawdown (from the "Info" side list) |
| `leverage_chart` | JSON array of daily leverage bars: `[{"value": "0", "date": "2026-02-01"}, ...]`. **`date` is estimated** from each bar's position on the chart's x-axis, assuming month ticks sit on the 1st; it may be off by a constant number of days, and is missing if no axis labels could be read. |

**Instruments tab**

| Column | Description |
|---|---|
| `instruments` | JSON object, symbol → number of trades, from the donut legend (assumes the default "Count" view). Example: `{"BTCUSD": "24", "XAUUSD": "7"}`. |
| `trade_statistics` | JSON object of the Trade Statistics list, using the site's own labels as keys. Example: `{"Best trade": "$94.19", ...}`. Keys depend on what the site shows. |

---

## Binance

### `data/binance/portfolio_urls.csv` (Phase 1)

| Column | Description |
|---|---|
| `portfolio_id` | Numeric ID from the profile link (`/lead-details/<id>`). Unique key. |
| `profile_url` | Full `binance.com` profile URL. Unique key. |
| `page_number` | Leaderboard page where the card was found. |
| `scraped_at` | UTC timestamp. |

Phase 1 doesn't collect the name; it comes from the profile page in Phase 2.

### `data/binance/trader_details.csv` (Phase 2)

**Header and identity**

| Column | Description |
|---|---|
| `portfolio_id`, `profile_url` | From Phase 1. |
| `name` | Trader's display name. |
| `level` | Badge level next to the name (e.g. "Legend"). |
| `description` | Trader's bio text. |
| `leverage` | Leverage tag from the tag row, as shown on the site. |
| `tradfi` | `True` if the trader has the "TradFi" tag. |
| `api_trading` | `True` if the trader has the "API Trading" tag. |
| `tags` | JSON array of the other achievement tags, e.g. `["Top Performer", "Money Maker", "Most Resilient"]`. |

**Stat row**

| Column | Site label |
|---|---|
| `days_trading` | Days Trading |
| `copiers` | Copiers (current; may be shown as `current/max`) |
| `total_copiers` | Total Copiers (all-time) |
| `mock_copiers` | Mock Copiers. Saved as `"0"` when the site hides the value, which it does for zero. |
| `closed_portfolios` | Closed Portfolios |
| `mock_copy_available` | `True` if the "Mock Copy" button is shown (portfolio is open to copying). |

**Performance panel**

| Column | Site label |
|---|---|
| `roi` | ROI |
| `pnl` | PnL |
| `copier_pnl` | Copier PnL: total profit/loss of the people copying this trader. |
| `sharpe_ratio` | Sharpe Ratio |
| `mdd` | MDD (maximum drawdown) |
| `win_rate` | Win Rate |
| `win_positions` | Win Positions |
| `total_positions` | Total Positions |

These reflect whichever time range the page shows by default.

**Lead Trader Overview panel**

| Column | Site label |
|---|---|
| `aum` | AUM (assets under management) |
| `profit_sharing` | Profit Sharing: % of copiers' profit paid to the trader. |
| `leading_margin_balance` | Leading Margin Balance |
| `lock_up_period` | Lock-up period |
| `minimum_copy_amount` | Minimum Copy Amount |

**JSON columns**

| Column | Description |
|---|---|
| `asset_preferences` | JSON object, asset → share of trading, from the Asset Preferences donut. Example: `{"ZEC": "54.08%", "BNB": "12.43%"}`. |
| `roi_chart` | JSON array of the ROI time series: `[{"date": "2026-09-16", "value": 0}, ...]`. Taken from the chart's own data request, so values are exact numbers (not text) and dates are UTC. Empty `[]` if the request wasn't captured. |
| `position_history` | JSON array of every closed position: `{"symbol", "tags", "status", "fields"}`. `tags` holds chips like `["Perp", "6X", "Cross Long"]`; `fields` maps the site's labels to values, e.g. `"Opened"`, `"Entry Price"`, `"Max. Open Interest"`, `"Closing PNL"`, `"Closed"`, `"Avg. Close Price"`, `"Closed Vol."`. Labels can differ between position types. |
| `is_private_portfolio` | `True` if the trader hides their history. Use it to tell "private" (`True`, `position_history` = `[]`) apart from "no closed positions" or "failed to load" (`False`, `[]`). |
| `copy_traders` | JSON array of every row of the Copy Traders table, all pages. Keys are the table's headers, e.g. `{"User ID": "Tan***ian", "Copy Margin Balance": "64.74 USDT", "Total PNL": "+5.89 USDT", "Total ROI": "+9.81%", "Duration": "27 Days"}`. `[]` usually means zero copiers. |
| `scraped_at` | UTC timestamp. |

---

## Comparing brokers

The two brokers don't share a schema. Rough equivalents for cross-broker analysis:

| Concept | FP Markets | Binance |
|---|---|---|
| Trader ID | `trader_id` | `portfolio_id` |
| Total return | `return_total` / `return_all_time` | `roi` |
| Max drawdown | `trading_max_drawdown` | `mdd` |
| Sharpe ratio | `trading_sharpe_ratio` | `sharpe_ratio` |
| Track record length | `age_days` | `days_trading` |
| Instruments traded | `instruments` (trade counts) | `asset_preferences` (% share) |
| Return over time | `monthly_chart` (monthly) | `roi_chart` (daily) |

Time windows and definitions may differ between sites, so check them before comparing directly.
