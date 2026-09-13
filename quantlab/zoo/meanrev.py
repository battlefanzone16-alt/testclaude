"""Retour à la moyenne MONO-ACTIF : chaque token est jugé sur lui seul.

Aucun classement entre tokens, aucune jambe de couverture sur un autre actif.
La décision pour un token n'utilise que son propre historique.

Justification par la mesure (ratio de variance, 86 perps liquides, 2022-2026,
chaque token pris isolément) :
    8 h 0,991 | 1 j 0,977 | 2 j 0,950 | 15 j 0,920 | 30 j 0,870
Tout est sous 1 et décroît avec l'horizon : un actif crypto seul ne continue
pas, il revient. Les 42 stratégies de suivi de tendance pariaient à l'envers.
L'autocorrélation à 1 jour vaut -0,030 (t médian -3,06, 65 tokens sur 86
au-delà de |t|>2).
"""
from __future__ import annotations
import numpy as np
import pandas as pd


def _n(x, cap=2.0):
    """Écrête puis ramène dans [-1, 1] : évite qu'un choc dicte tout le livre."""
    return x.clip(-cap, cap) / cap


def z_ma(close, n, cap=2.0):
    """Écart à sa propre moyenne, en écarts-types. Contrarien : on vend l'écart."""
    m = close.rolling(n, min_periods=n // 2).mean()
    s = close.rolling(n, min_periods=n // 2).std()
    return -_n((close - m) / s.replace(0.0, np.nan), cap)


def ret_rev(close, n, w=180, cap=2.0):
    """Rendement passé sur n barres, normalisé par la volatilité. Contrarien."""
    r = np.log(close).diff(n)
    v = np.log(close).diff().rolling(w, min_periods=w // 3).std() * np.sqrt(n)
    return -_n(r / v.replace(0.0, np.nan), cap)


def rsi_rev(close, n):
    """RSI de Wilder recentré : positif quand survendu."""
    d = close.diff()
    up = d.clip(lower=0).ewm(alpha=1 / n, adjust=False, min_periods=n).mean()
    dn = (-d).clip(lower=0).ewm(alpha=1 / n, adjust=False, min_periods=n).mean()
    rsi = 100 - 100 / (1 + up / dn.replace(0.0, np.nan))
    return (50.0 - rsi) / 50.0


def range_rev(close, high, low, n):
    """Position dans la fourchette des n barres. +1 au plus bas, -1 au plus haut."""
    h = high.rolling(n, min_periods=n // 2).max()
    l = low.rolling(n, min_periods=n // 2).min()
    return 1.0 - 2.0 * (close - l) / (h - l).replace(0.0, np.nan)


def dist_ma(close, n, w=180, cap=2.0):
    """Distance relative à la moyenne, mise à l'échelle de la volatilité."""
    m = close.rolling(n, min_periods=n // 2).mean()
    v = np.log(close).diff().rolling(w, min_periods=w // 3).std() * np.sqrt(n)
    return -_n((close / m - 1.0) / v.replace(0.0, np.nan), cap)
