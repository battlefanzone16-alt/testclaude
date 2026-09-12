"""Performance statistics, including the ones that survive contact with
a multiple-testing critique (PSR / Deflated Sharpe).
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import stats


def _arr(r) -> np.ndarray:
    a = np.asarray(r, dtype=float)
    return a[np.isfinite(a)]


def sharpe(returns, periods_per_year: float, rf: float = 0.0) -> float:
    """Annualised Sharpe of a per-bar simple-return series."""
    r = _arr(returns)
    if r.size < 2:
        return 0.0
    excess = r - rf / periods_per_year
    sd = excess.std(ddof=1)
    if sd <= 1e-12:
        return 0.0
    return float(excess.mean() / sd * np.sqrt(periods_per_year))


def sortino(returns, periods_per_year: float) -> float:
    r = _arr(returns)
    if r.size < 2:
        return 0.0
    downside = r[r < 0]
    if downside.size < 2:
        return 0.0
    dd = np.sqrt(np.mean(downside ** 2))
    if dd <= 1e-12:
        return 0.0
    return float(r.mean() / dd * np.sqrt(periods_per_year))


def equity_curve(returns) -> np.ndarray:
    r = np.asarray(returns, dtype=float)
    r = np.nan_to_num(r)
    return np.cumprod(1.0 + r)


def max_drawdown(returns) -> float:
    """Max peak-to-trough drawdown of the compounded curve, as a positive fraction."""
    eq = equity_curve(returns)
    if eq.size == 0:
        return 0.0
    peak = np.maximum.accumulate(eq)
    dd = eq / peak - 1.0
    return float(-dd.min())


def cagr(returns, periods_per_year: float) -> float:
    r = _arr(returns)
    if r.size == 0:
        return 0.0
    total = float(np.prod(1.0 + r))
    years = r.size / periods_per_year
    if years <= 0 or total <= 0:
        return -1.0
    return float(total ** (1.0 / years) - 1.0)


def calmar(returns, periods_per_year: float) -> float:
    mdd = max_drawdown(returns)
    if mdd <= 1e-9:
        return 0.0
    return float(cagr(returns, periods_per_year) / mdd)


def probabilistic_sharpe(observed_sr: float, n: int, skew: float, kurt: float,
                         benchmark_sr: float = 0.0) -> float:
    """PSR: P(true SR > benchmark) given the sample's higher moments.

    observed_sr and benchmark_sr are *per-bar* (non-annualised) Sharpe ratios.
    Bailey & Lopez de Prado (2012).
    """
    if n < 3:
        return 0.0
    denom = 1.0 - skew * observed_sr + (kurt - 1.0) / 4.0 * observed_sr ** 2
    if denom <= 0:
        return 0.0
    z = (observed_sr - benchmark_sr) * np.sqrt(n - 1) / np.sqrt(denom)
    return float(stats.norm.cdf(z))


def deflated_sharpe(observed_sr: float, n: int, skew: float, kurt: float,
                    n_trials: int, sr_variance_across_trials: float) -> float:
    """Deflated Sharpe Ratio: PSR against the SR you would expect from the
    *best* of `n_trials` independent backtests on pure noise.

    This is the number that answers "is my 1.8 Sharpe just the max of 500
    parameter combos?". observed_sr / variance are per-bar.
    """
    if n_trials < 2 or sr_variance_across_trials <= 0:
        return probabilistic_sharpe(observed_sr, n, skew, kurt, 0.0)
    e = np.euler_gamma
    # Expected maximum of n_trials draws from N(0, var) — Gumbel approximation.
    z1 = stats.norm.ppf(1.0 - 1.0 / n_trials)
    z2 = stats.norm.ppf(1.0 - 1.0 / (n_trials * np.e))
    sr0 = np.sqrt(sr_variance_across_trials) * ((1.0 - e) * z1 + e * z2)
    return probabilistic_sharpe(observed_sr, n, skew, kurt, float(sr0))


def trade_stats(returns, positions) -> dict:
    """Per-trade aggregates. A 'trade' is a maximal run of constant non-zero position."""
    r = np.nan_to_num(np.asarray(returns, dtype=float))
    p = np.nan_to_num(np.asarray(positions, dtype=float))
    n = min(r.size, p.size)
    r, p = r[:n], p[:n]

    trades, start = [], None
    for i in range(n):
        if p[i] != 0 and start is None:
            start = i
        elif start is not None and (p[i] == 0 or np.sign(p[i]) != np.sign(p[start])):
            trades.append(float(np.prod(1.0 + r[start:i]) - 1.0))
            start = i if p[i] != 0 else None
    if start is not None:
        trades.append(float(np.prod(1.0 + r[start:n]) - 1.0))

    if not trades:
        return {"n_trades": 0, "win_rate": 0.0, "profit_factor": 0.0,
                "avg_trade": 0.0, "best": 0.0, "worst": 0.0}
    t = np.array(trades)
    wins, losses = t[t > 0], t[t < 0]
    gross_win, gross_loss = wins.sum(), -losses.sum()
    return {
        "n_trades": int(t.size),
        "win_rate": float((t > 0).mean()),
        "profit_factor": float(gross_win / gross_loss) if gross_loss > 1e-12 else float("inf"),
        "avg_trade": float(t.mean()),
        "best": float(t.max()),
        "worst": float(t.min()),
    }


def summary(returns, positions=None, periods_per_year: float = 252.0) -> dict:
    """One-stop stat block for a per-bar return series."""
    r = _arr(returns)
    sr = sharpe(r, periods_per_year)
    out = {
        "sharpe": sr,
        "sortino": sortino(r, periods_per_year),
        "cagr": cagr(r, periods_per_year),
        "max_drawdown": max_drawdown(r),
        "calmar": calmar(r, periods_per_year),
        "vol_annual": float(r.std(ddof=1) * np.sqrt(periods_per_year)) if r.size > 1 else 0.0,
        "skew": float(stats.skew(r)) if r.size > 2 else 0.0,
        "kurtosis": float(stats.kurtosis(r, fisher=False)) if r.size > 3 else 3.0,
        "n_bars": int(r.size),
    }
    sr_bar = sr / np.sqrt(periods_per_year) if periods_per_year > 0 else 0.0
    out["psr"] = probabilistic_sharpe(sr_bar, r.size, out["skew"], out["kurtosis"])
    if positions is not None:
        out.update(trade_stats(returns, positions))
        p = np.nan_to_num(np.asarray(positions, dtype=float))
        out["exposure"] = float((p != 0).mean()) if p.size else 0.0
    return out
