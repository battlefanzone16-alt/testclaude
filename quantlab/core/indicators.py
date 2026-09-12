"""Indicateurs répliqués de TradingView.

Deux pièges sont traités explicitement ici :

1. Le Kalman de BackQuant est un scalaire 1D. Son gain converge vers
   K* = (-PN + sqrt(PN^2 + 4*PN*MN)) / 2 / ... soit ~0.0311 pour PN=0.001, MN=1,
   ce qui équivaut à une EMA-63. On implémente la récursion complète (pas l'état
   stationnaire) pour que le warm-up colle à TradingView.

2. Les pivots de Donchian "Pivot High-Low" ne sont CONNUS que pvtLenR bougies
   après la bougie du pivot. Forward-filler depuis la bougie du pivot injecte du
   lookahead. Ici la valeur n'est publiée qu'à partir de i + pvtLenR.
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def kalman_bq(close, process_noise: float = 0.001, measurement_noise: float = 1.0):
    """Kalman Price Filter (© BackQuant, v5), scalaire 1D sur le close.

    predict : P = P + PN
    update  : K = P / (P + MN) ; x += K*(z - x) ; P = (1-K)*P
    """
    z = np.asarray(close, dtype=float)
    n = z.size
    out = np.full(n, np.nan)
    if n == 0:
        return out

    # Premier échantillon valide = état initial, incertitude = 1.
    first = int(np.argmax(np.isfinite(z))) if np.isfinite(z).any() else -1
    if first < 0:
        return out

    x = z[first]
    P = 1.0
    out[first] = x
    for i in range(first + 1, n):
        if not np.isfinite(z[i]):
            out[i] = x
            continue
        P = P + process_noise
        K = P / (P + measurement_noise)
        x = x + K * (z[i] - x)
        P = (1.0 - K) * P
        out[i] = x
    return out


def kalman_gain_steady(process_noise: float = 0.001, measurement_noise: float = 1.0) -> float:
    """Gain stationnaire du filtre — utile pour vérifier l'équivalence EMA."""
    pn, mn = process_noise, measurement_noise
    p = (-pn + np.sqrt(pn * pn + 4.0 * pn * mn)) / 2.0
    return float((p + pn) / (p + pn + mn))


def pivot_high(high, left: int, right: int):
    """Pivot haut confirmé, publié avec `right` bougies de retard.

    Retourne un tableau où la case i contient le prix du dernier pivot haut
    CONNU à la clôture de la bougie i (NaN tant qu'aucun pivot n'est confirmé).
    """
    h = np.asarray(high, dtype=float)
    n = h.size
    out = np.full(n, np.nan)
    last = np.nan
    for i in range(n):
        # A la bougie i, on peut confirmer le pivot candidat situé en i-right.
        c = i - right
        if c - left >= 0:
            win = h[c - left: c + right + 1]
            if np.isfinite(h[c]) and np.isfinite(win).all() and h[c] == win.max():
                # Strict sur la gauche pour éviter de re-déclencher sur un plateau.
                if not np.any(h[c - left:c] > h[c]) and not np.any(h[c + 1:c + right + 1] >= h[c]):
                    last = h[c]
        out[i] = last
    return out


def pivot_low(low, left: int, right: int):
    """Pivot bas confirmé, publié avec `right` bougies de retard."""
    l = np.asarray(low, dtype=float)
    n = l.size
    out = np.full(n, np.nan)
    last = np.nan
    for i in range(n):
        c = i - right
        if c - left >= 0:
            win = l[c - left: c + right + 1]
            if np.isfinite(l[c]) and np.isfinite(win).all() and l[c] == win.min():
                if not np.any(l[c - left:c] < l[c]) and not np.any(l[c + 1:c + right + 1] <= l[c]):
                    last = l[c]
        out[i] = last
    return out


def donchian_combined(high, low, length: int = 20, pvt_left: int = 2, pvt_right: int = 4):
    """Donchian Channel "Pivot High-Low" mode Combined (© HeWhoMustNotBeNamed v4).

    Combine le Donchian sur pivots (forward-fill, sans lookahead) avec le
    Donchian classique. Retourne (upper, lower, median).
    """
    h = pd.Series(np.asarray(high, dtype=float))
    l = pd.Series(np.asarray(low, dtype=float))

    # Donchian classique.
    high_c = h.rolling(length, min_periods=length).max().to_numpy()
    low_c = l.rolling(length, min_periods=length).min().to_numpy()
    middle_c = (high_c + low_c) / 2.0

    # Donchian sur pivots confirmés.
    high_p = pivot_high(h.to_numpy(), pvt_left, pvt_right)
    low_p = pivot_low(l.to_numpy(), pvt_left, pvt_right)
    middle_p = (high_p + low_p) / 2.0

    upper = (high_p + high_c) / 2.0
    lower = (low_p + low_c) / 2.0
    median = (middle_p + middle_c) / 2.0
    return upper, lower, median


def atr(high, low, close, length: int = 14):
    """ATR de Wilder (RMA), aligné sur la définition TradingView."""
    h = np.asarray(high, dtype=float)
    l = np.asarray(low, dtype=float)
    c = np.asarray(close, dtype=float)
    prev = np.concatenate(([np.nan], c[:-1]))
    tr = np.nanmax(np.vstack([h - l, np.abs(h - prev), np.abs(l - prev)]), axis=0)
    return pd.Series(tr).ewm(alpha=1.0 / length, adjust=False, min_periods=length).mean().to_numpy()


def ema(x, length: int):
    return pd.Series(np.asarray(x, dtype=float)).ewm(
        span=length, adjust=False, min_periods=length).mean().to_numpy()
