"""Modèle de coût par token, calibré sur des spreads MESURÉS.

Le dépôt suppose un spread unique (0,02 % × 3) pour tous les tokens. La mesure
sur les archives bookTicker de Binance montre un facteur 46 entre SOL (0,27 bps)
et DGB (12,5 bps) : un spread global est faux pour tout le monde à la fois.

Ici le spread d'un token à une date est le maximum de deux termes :
  - un terme de liquidité, ajusté sur log(spread) ~ a + b·log(notionnel/jour) ;
  - un plancher de tick, 1 tick / prix — contraignant sur les tokens à petit prix,
    où le spread ne PEUT pas descendre sous un pas de cotation.

Grilles de frais (par côté, perpétuels, palier de base, septembre 2026) :
    Binance USDⓈ-M   maker 0,020 %   taker 0,050 %
    Hyperliquid      maker 0,015 %   taker 0,045 %
    Lighter          maker 0      %  taker 0      %   (comptes Standard)
"""
from __future__ import annotations
import numpy as np
import pandas as pd

FEES = {                      # (maker, taker) par côté, en fraction
    "binance":     (0.00020, 0.00050),
    "hyperliquid": (0.00015, 0.00045),
    "lighter":     (0.0,     0.0),
}

# Ajustement log-log sur 15 tokens mesurés (bookTicker, 3 journées 2023-2024).
SPREAD_A, SPREAD_B = None, None       # renseignés par fit_spread_model()


def fit_spread_model(notional_musd, spread_bps):
    """log(spread_bps) = a + b·log(notionnel M$). Renvoie (a, b, R²)."""
    x = np.log(np.asarray(notional_musd, float))
    y = np.log(np.asarray(spread_bps, float))
    b, a = np.polyfit(x, y, 1)
    r2 = 1 - ((y - (a + b * x)) ** 2).sum() / ((y - y.mean()) ** 2).sum()
    return float(a), float(b), float(r2)


def infer_tick(close: pd.Series) -> float:
    """Pas de cotation déduit du nombre de décimales effectivement utilisées."""
    v = close.dropna().to_numpy()
    if len(v) == 0:
        return np.nan
    for d in range(0, 11):                      # plus petite précision qui suffit
        if np.allclose(v, np.round(v, d), rtol=0, atol=1e-12):
            return 10.0 ** (-d)
    return 10.0 ** (-10)


def spread_panel(close: pd.DataFrame, volume: pd.DataFrame, a: float, b: float,
                 win=180, floor_bps=0.2, cap_bps=60.0) -> pd.DataFrame:
    """Spread par token et par barre, en fraction du prix (aller simple = spread/2)."""
    notional = (close * volume).rolling(win, min_periods=win // 3).median() * 6 / 1e6
    liq = np.exp(a + b * np.log(notional.clip(lower=0.05)))
    tick = pd.Series({c: infer_tick(close[c]) for c in close.columns})
    tick_bps = (tick / close) * 1e4                    # 1 tick, en bps du prix
    sp = np.maximum(liq, tick_bps).clip(lower=floor_bps, upper=cap_bps)
    return sp / 1e4


def cost_panel(spread: pd.DataFrame, venue="binance", style="taker") -> pd.DataFrame:
    """Coût par côté = frais + (spread/2 si on traverse le carnet)."""
    maker, taker = FEES[venue]
    fee = maker if style == "maker" else taker
    cross = 0.0 if style == "maker" else 0.5
    return fee + cross * spread
