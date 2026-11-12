import math

import pandas as pd
import pytest

from analysis.shared import performance_metrics as pm


def series(*values):
    return pd.Series(values, dtype=float)


def test_compounded_return_compounds_instead_of_summing():
    assert pm.compounded_return(series(0.5, -0.5)) == pytest.approx(-0.25)


def test_cagr_annualizes_and_floors_at_total_loss():
    assert pm.cagr(0.21, 2 * 365.25) == pytest.approx(0.10)
    assert pm.cagr(-1.0, 100) == -1.0
    assert math.isnan(pm.cagr(0.1, 0))


def test_sharpe_does_not_grow_with_track_record_length():
    short = series(0.02, 0.01, 0.03, -0.01)
    long = pd.concat([short] * 6, ignore_index=True)
    assert pm.sharpe_ratio(long) == pytest.approx(pm.sharpe_ratio(short), rel=0.15)


def test_sharpe_is_nan_for_constant_returns():
    assert math.isnan(pm.sharpe_ratio(series(0.01, 0.01, 0.01)))


def test_sortino_ignores_upside_volatility():
    assert math.isnan(pm.sortino_ratio(series(0.01, 0.10, 0.02)))
    assert pm.sortino_ratio(series(0.05, -0.02, 0.03)) > pm.sharpe_ratio(series(0.05, -0.02, 0.03))


def test_max_drawdown_includes_a_loss_in_the_first_period():
    assert pm.max_drawdown(series(-0.10, 0.05)) == pytest.approx(0.10)
    assert pm.max_drawdown(series(0.10, -0.50, 0.20)) == pytest.approx(0.50)


def test_omega_and_profit_factor_avoid_infinity():
    assert math.isnan(pm.omega_ratio(series(0.01, 0.02)))
    assert math.isnan(pm.profit_factor(10, 0, 5.0, 0.0))


def test_trade_metrics_handle_negative_average_loss():
    # 60% win rate, wins 1.0, losses -1.0 -> expectancy +0.2R, profit factor 1.5.
    assert pm.expectancy_r(6, 4, 1.0, -1.0) == pytest.approx(0.2)
    assert pm.expectancy_r(6, 4, 1.0, 1.0) == pytest.approx(0.2)
    assert pm.profit_factor(6, 4, 1.0, -1.0) == pytest.approx(1.5)
    assert pm.kelly_fraction(6, 4, 1.0, -1.0) == pytest.approx(0.2)


def test_probabilistic_sharpe_is_a_probability_that_rises_with_history():
    short = series(0.03, -0.01, 0.02, 0.01, -0.005, 0.02)
    long = pd.concat([short] * 4, ignore_index=True)
    psr_short, psr_long = pm.probabilistic_sharpe_ratio(short), pm.probabilistic_sharpe_ratio(long)
    assert 0 < psr_short < psr_long <= 1


def test_composite_score_respects_direction_and_penalizes_missing():
    frame = pd.DataFrame({"good": [1.0, 2.0, None], "bad": [3.0, 1.0, 2.0]})
    score = pm.composite_score(frame, {"good": 1, "bad": -1})
    assert score.idxmax() == 1
    assert score.iloc[2] < score.iloc[1]
