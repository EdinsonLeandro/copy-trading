"""Broker-agnostic performance and risk metrics for copy-trading strategies.

Every return-series function takes a ``pd.Series`` of **monthly returns as
decimal fractions** (0.05 == +5%), oldest first. Annualization assumes 12
periods per year. A risk-free rate of 0 is used throughout: copy-trading
capital sits in a broker account that earns nothing, so 0 is the honest
hurdle, and it keeps the ratios comparable with the brokers' own figures.

Undefined results (zero volatility, no losing trades, too few observations)
come back as ``NaN`` rather than ``inf``, so they can never float to the top
of a ranking by accident.
"""

from __future__ import annotations

import math

import numpy as np
import pandas as pd

PERIODS_PER_YEAR = 12
DAYS_PER_YEAR = 365.25


# --- Return-series metrics -------------------------------------------------


def equity_curve(returns: pd.Series) -> pd.Series:
    """Growth of 1 unit of capital, compounded period by period."""
    return (1 + returns).cumprod()


def compounded_return(returns: pd.Series) -> float:
    """Total time-weighted return. Compounds, never sums: +50% then -50% is -25%."""
    if returns.empty:
        return float("nan")
    return float((1 + returns).prod() - 1)


def cagr(total_return: float, days: float) -> float:
    """Annualized compound growth rate from a total return over ``days``."""
    if pd.isna(total_return) or not days or days <= 0:
        return float("nan")
    growth = 1 + total_return
    if growth <= 0:
        return -1.0
    return float(growth ** (DAYS_PER_YEAR / days) - 1)


def annualized_volatility(returns: pd.Series) -> float:
    """Sample standard deviation of returns, scaled to one year."""
    if len(returns) < 2:
        return float("nan")
    return float(returns.std(ddof=1) * math.sqrt(PERIODS_PER_YEAR))


def sharpe_ratio(returns: pd.Series) -> float:
    """Annualized Sharpe ratio: mean / std of the *same* periodic returns, x sqrt(12).

    Uses the mean, not the total, so it doesn't grow just because a track record is
    longer (the flaw in summing returns and dividing by their std).
    """
    if len(returns) < 2:
        return float("nan")
    std = returns.std(ddof=1)
    if std == 0 or pd.isna(std):
        return float("nan")
    return float(returns.mean() / std * math.sqrt(PERIODS_PER_YEAR))


def downside_deviation(returns: pd.Series, target: float = 0.0) -> float:
    """Root-mean-square shortfall below ``target``, over *all* periods (Sortino's definition)."""
    if returns.empty:
        return float("nan")
    shortfall = np.minimum(returns - target, 0.0)
    return float(math.sqrt((shortfall**2).mean()))


def sortino_ratio(returns: pd.Series, target: float = 0.0) -> float:
    """Annualized Sortino ratio: like Sharpe, but only penalizes downside volatility."""
    if len(returns) < 2:
        return float("nan")
    dd = downside_deviation(returns, target)
    if dd == 0 or pd.isna(dd):
        return float("nan")
    return float((returns.mean() - target) / dd * math.sqrt(PERIODS_PER_YEAR))


def drawdown_series(returns: pd.Series) -> pd.Series:
    """Fractional distance below the running peak of the equity curve (0 == at a new high)."""
    curve = equity_curve(returns)
    # The account starts at 1.0, so a loss in the very first period is a drawdown too.
    peak = np.maximum(curve.cummax(), 1.0)
    return 1 - curve / peak


def max_drawdown(returns: pd.Series) -> float:
    """Largest peak-to-trough loss as a positive fraction (0.25 == -25%)."""
    if returns.empty:
        return float("nan")
    return float(drawdown_series(returns).max())


def ulcer_index(returns: pd.Series) -> float:
    """RMS of drawdown depth: punishes drawdowns that are both deep *and* long."""
    if returns.empty:
        return float("nan")
    return float(math.sqrt((drawdown_series(returns) ** 2).mean()))


def calmar_ratio(annual_return: float, max_dd: float) -> float:
    """Annualized return per unit of maximum drawdown."""
    if pd.isna(annual_return) or pd.isna(max_dd) or max_dd <= 0:
        return float("nan")
    return float(annual_return / max_dd)


def omega_ratio(returns: pd.Series, threshold: float = 0.0) -> float:
    """Sum of gains above ``threshold`` over sum of losses below it (uses the whole distribution)."""
    if returns.empty:
        return float("nan")
    gains = np.maximum(returns - threshold, 0.0).sum()
    losses = np.maximum(threshold - returns, 0.0).sum()
    if losses == 0:
        return float("nan")
    return float(gains / losses)


def positive_period_share(returns: pd.Series) -> float:
    """Fraction of periods with a strictly positive return."""
    if returns.empty:
        return float("nan")
    return float((returns > 0).mean())


def _normal_cdf(x: float) -> float:
    return 0.5 * (1 + math.erf(x / math.sqrt(2)))


def probabilistic_sharpe_ratio(returns: pd.Series, benchmark_sharpe: float = 0.0) -> float:
    """Probability that the true (per-period) Sharpe exceeds ``benchmark_sharpe``.

    Bailey & Lopez de Prado (2012). Corrects the observed Sharpe for track-record
    length, skew and fat tails, which matters here: most strategies have under a
    year of history, and grid/martingale styles have heavily negative skew.
    """
    n = len(returns)
    if n < 3:
        return float("nan")
    std = returns.std(ddof=1)
    if std == 0 or pd.isna(std):
        return float("nan")
    sr = returns.mean() / std
    skew = returns.skew()
    kurtosis = returns.kurt() + 3  # pandas returns *excess* kurtosis
    if pd.isna(skew) or pd.isna(kurtosis):
        return float("nan")
    variance = 1 - skew * sr + (kurtosis - 1) / 4 * sr**2
    if variance <= 0:
        return float("nan")
    return _normal_cdf((sr - benchmark_sharpe) * math.sqrt(n - 1) / math.sqrt(variance))


# --- Trade-statistics metrics (currency-invariant) ---------------------------
# Ratios of amounts in the same account currency cancel the currency out, so
# these are comparable across traders even though their raw P&L figures aren't.


def win_rate(won: float, lost: float) -> float:
    total = won + lost
    if not total:
        return float("nan")
    return float(won / total)


def payoff_ratio(avg_win: float, avg_loss: float) -> float:
    """Average winning trade over the absolute average losing trade."""
    if pd.isna(avg_win) or pd.isna(avg_loss) or avg_loss == 0:
        return float("nan")
    return float(avg_win / abs(avg_loss))


def profit_factor(won: float, lost: float, avg_win: float, avg_loss: float) -> float:
    """Gross profit over gross loss. >1 means the strategy has made money."""
    gross_loss = lost * abs(avg_loss)
    if pd.isna(gross_loss) or gross_loss == 0:
        return float("nan")
    return float(won * avg_win / gross_loss)


def expectancy_r(won: float, lost: float, avg_win: float, avg_loss: float) -> float:
    """Expected profit per trade in units of the average loss ("R multiples").

    ``p_win * payoff - p_loss``: +0.2 means each trade earns, on average, 20% of
    what a typical losing trade costs. Signs are explicit, because ``avg_loss``
    may arrive either positive or negative.
    """
    p_win = win_rate(won, lost)
    payoff = payoff_ratio(avg_win, avg_loss)
    if pd.isna(p_win) or pd.isna(payoff):
        return float("nan")
    return float(p_win * payoff - (1 - p_win))


def kelly_fraction(won: float, lost: float, avg_win: float, avg_loss: float) -> float:
    """Kelly-optimal fraction of capital per trade: ``p - (1 - p) / payoff``. <=0 means no edge."""
    p_win = win_rate(won, lost)
    payoff = payoff_ratio(avg_win, avg_loss)
    if pd.isna(p_win) or pd.isna(payoff) or payoff == 0:
        return float("nan")
    return float(p_win - (1 - p_win) / payoff)


# --- Ranking -----------------------------------------------------------------


def composite_score(frame: pd.DataFrame, weights: dict[str, float]) -> pd.Series:
    """Weighted average of percentile ranks, on a 0-100 scale.

    ``weights`` maps column -> weight; a negative weight means "lower is better".
    Percentile ranks make metrics on wildly different scales comparable and are
    robust to the extreme outliers in this data. A missing metric scores 0 for
    that component (unknown is not rewarded), and ties share the average rank.
    """
    total_weight = sum(abs(w) for w in weights.values())
    score = pd.Series(0.0, index=frame.index)
    for column, weight in weights.items():
        pct = frame[column].rank(pct=True, ascending=weight > 0, method="average")
        score += abs(weight) * pct.fillna(0.0)
    return 100 * score / total_weight
