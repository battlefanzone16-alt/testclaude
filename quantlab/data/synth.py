"""Générateur de données synthétiques multi-tokens type crypto.

Sert UNIQUEMENT à valider que la chaîne (moteur -> portefeuille -> Monte Carlo)
est correcte et sans biais. Aucun résultat de performance obtenu ici n'a de
valeur prédictive : c'est du bruit calibré, pas du marché.

Propriétés reproduites : marche aléatoire géométrique avec vol clustering
(GARCH-like), queues épaisses (Student-t), bêta commun à un facteur "BTC",
et régimes de tendance persistants.
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def _garch_t_returns(n, rng, base_vol, nu=4.0, alpha=0.08, beta=0.90, drift=0.0):
    """Rendements à vol clustering et queues épaisses."""
    omega = base_vol ** 2 * (1.0 - alpha - beta)
    var = base_vol ** 2
    out = np.empty(n)
    shocks = rng.standard_t(nu, n) / np.sqrt(nu / (nu - 2.0))
    for i in range(n):
        var = omega + alpha * out[i - 1] ** 2 + beta * var if i > 0 else var
        out[i] = np.sqrt(var) * shocks[i]
    return out + drift


def _regime_drift(n, rng, bars_per_regime=400, strength=0.0006):
    """Régimes de tendance persistants (bull / bear / range)."""
    d = np.zeros(n)
    i = 0
    while i < n:
        L = max(50, int(rng.exponential(bars_per_regime)))
        state = rng.choice([1, -1, 0], p=[0.35, 0.3, 0.35])
        d[i:i + L] = state * strength * rng.uniform(0.5, 1.5)
        i += L
    return d


def make_token(n_bars, rng, base_vol=0.012, beta=0.8, market=None, start=100.0):
    """Construit une série OHLCV H4 pour un token."""
    idio = _garch_t_returns(n_bars, rng, base_vol)
    drift = _regime_drift(n_bars, rng)
    r = idio + drift
    if market is not None:
        r = beta * market + np.sqrt(max(1e-9, 1.0 - beta ** 2 * 0.5)) * r

    close = start * np.exp(np.cumsum(r))
    # OHLC cohérents : la mèche est proportionnelle à la vol locale de la bougie.
    wick = np.abs(r) * rng.uniform(0.4, 1.4, n_bars) + base_vol * 0.35
    open_ = np.concatenate(([start], close[:-1]))
    high = np.maximum(open_, close) * (1.0 + wick * rng.uniform(0.2, 1.0, n_bars))
    low = np.minimum(open_, close) * (1.0 - wick * rng.uniform(0.2, 1.0, n_bars))
    vol = rng.lognormal(10, 1, n_bars)
    return pd.DataFrame({"open": open_, "high": high, "low": low,
                         "close": close, "volume": vol})


def make_universe(n_tokens=30, n_bars=4380, seed=7, start_date="2024-01-01"):
    """Univers synthétique multi-tokens avec un facteur de marché commun.

    n_bars=4380 ~= 2 ans de H4 (6 bougies/jour * 365 * 2).
    """
    rng = np.random.default_rng(seed)
    idx = pd.date_range(start_date, periods=n_bars, freq="4h")
    market = _garch_t_returns(n_bars, rng, 0.010) + _regime_drift(n_bars, rng, 600, 0.0005)

    out = {}
    for k in range(n_tokens):
        beta = float(rng.uniform(0.5, 1.1))
        bv = float(rng.uniform(0.008, 0.022))
        df = make_token(n_bars, rng, base_vol=bv, beta=beta, market=market,
                        start=float(rng.uniform(0.5, 500)))
        df.index = idx
        df.index.name = "timestamp"
        out[f"SYN{k:02d}USDT"] = df
    return out
