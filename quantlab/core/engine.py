"""Moteur de backtest mono-token du système Kalman v6.

Conventions anti-biais :
  - Tous les indicateurs de la bougie i n'utilisent que l'information <= clôture i
    (les pivots Donchian sont publiés avec pvt_right bougies de retard).
  - La décision est prise à la clôture de la bougie i, l'exécution est comptée
    à ce même prix MAJORÉ DES COÛTS (frais + spread*mult), ce qui est la
    convention du système v5 (ordre marché à la clôture H4).
  - Le stop dur est vérifié en intrabar : dès que le low (long) de la bougie j
    touche le stop, on sort AU STOP, avant toute évaluation de sortie souple.
  - Le stop dur prime toujours sur la sortie souple dans la même bougie
    (hypothèse conservatrice : on ne sait pas l'ordre intrabar).

Sortie : un DataFrame de trades + un jeu de tableaux par bougie (levier signé,
coûts) que le module portefeuille agrège en une courbe d'équité réelle.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .config import Config
from .indicators import kalman_bq, donchian_combined, atr


def compute_signals(df: pd.DataFrame, cfg: Config) -> dict:
    """Indicateurs + croisements, alignés sur l'index de df."""
    close = df["close"].to_numpy(float)
    high = df["high"].to_numpy(float)
    low = df["low"].to_numpy(float)

    kal = kalman_bq(close, cfg.kalman_pn, cfg.kalman_mn)
    up, lo, med = donchian_combined(high, low, cfg.dc_length, cfg.pvt_left, cfg.pvt_right)
    a = atr(high, low, close, cfg.atr_length)

    prev_close = np.concatenate(([np.nan], close[:-1]))
    prev_kal = np.concatenate(([np.nan], kal[:-1]))
    cross_up = (close > kal) & (prev_close <= prev_kal)
    cross_dn = (close < kal) & (prev_close >= prev_kal)

    return {"close": close, "high": high, "low": low, "kal": kal,
            "upper": up, "lower": lo, "median": med, "atr": a,
            "cross_up": cross_up, "cross_dn": cross_dn}


def _hard_stop_price(i: int, side: int, s: dict, cfg: Config) -> float:
    """Prix du stop dur pour une entrée à la bougie i."""
    if cfg.sl_mode == "atr":
        a = s["atr"][i]
        if not np.isfinite(a) or a <= 0:
            return np.nan
        return s["close"][i] - side * cfg.sl_atr_mult * a
    if cfg.sl_mode == "donchian":
        b = s["lower"][i] if side > 0 else s["upper"][i]
        return b
    # "wick" : extrême de la bougie de cassure
    return s["low"][i] if side > 0 else s["high"][i]


def backtest_token(df: pd.DataFrame, cfg: Config, token: str = "TOKEN") -> dict:
    """Backtest un token. Retourne trades + séries par bougie."""
    s = compute_signals(df, cfg)
    n = len(df)
    close, high, low = s["close"], s["high"], s["low"]
    kal, med = s["kal"], s["median"]

    cost = cfg.cost_per_side_frac()

    lev_signed = np.zeros(n)     # notionnel signé / capital, AVANT scaling portefeuille
    cost_frac = np.zeros(n)      # coût payé à cette bougie, en fraction du notionnel
    trades = []

    # NOTE — le filtre « pente Kalman » est un NO-OP, comme le « Filter Order N »
    # du script TradingView. Avec kal[i] = kal[i-1] + K*(c[i]-kal[i-1]), 0<K<1 :
    #     c[i] > kal[i]      <=> c[i](1-K) > kal[i-1](1-K) <=> c[i] > kal[i-1]
    #     kal[i] > kal[i-1]  <=> K*(c[i]-kal[i-1]) > 0     <=> c[i] > kal[i-1]
    # Les deux conditions sont équivalentes : tout croisement haussier a déjà,
    # par construction, une pente Kalman positive. Vérifié empiriquement sur
    # 1377 croisements : 0 exception. Inutile de le tester comme une option.
    i = 0
    while i < n - 1:
        side = 0
        if cfg.enable_long and s["cross_up"][i] and np.isfinite(med[i]):
            if (not cfg.entry_above_median) or close[i] > med[i]:
                side = 1
        if side == 0 and cfg.enable_short and s["cross_dn"][i] and np.isfinite(med[i]):
            if (not cfg.entry_above_median) or close[i] < med[i]:
                side = -1
        if side == 0:
            i += 1
            continue

        entry = close[i]
        sl = _hard_stop_price(i, side, s, cfg)
        if not np.isfinite(sl) or not np.isfinite(entry) or entry <= 0:
            i += 1
            continue

        sl_dist = side * (entry - sl) / entry
        if not (sl_dist > 0):           # attrape NaN ET négatif (bug #3 du doc v5)
            i += 1
            continue
        if cfg.max_sl_dist is not None and sl_dist > cfg.max_sl_dist:
            i += 1
            continue
        if cfg.max_dist_kalman is not None:
            d = abs(entry - kal[i]) / entry
            if not np.isfinite(d) or d > cfg.max_dist_kalman:
                i += 1
                continue

        lev = min(cfg.risk_pct / sl_dist, cfg.max_lev)
        if lev <= 0:
            i += 1
            continue

        # --- vie du trade ---
        exit_idx, exit_px, reason = None, None, None
        for j in range(i + 1, n):
            # 1) stop dur intrabar (priorité absolue)
            hit = (low[j] <= sl) if side > 0 else (high[j] >= sl)
            if hit:
                exit_idx, exit_px, reason = j, sl, "SL_dur"
                break
            # 2) time stop (clôture)
            if cfg.time_stop_bars is not None and (j - i) >= cfg.time_stop_bars:
                exit_idx, exit_px, reason = j, close[j], "time_stop"
                break
            # 3) sortie souple par la médiane (clôture)
            if cfg.exit_on_median and np.isfinite(med[j]):
                if (side > 0 and close[j] < med[j]) or (side < 0 and close[j] > med[j]):
                    exit_idx, exit_px, reason = j, close[j], "clot_mediane"
                    break
            # 4) sortie souple par le Kalman (clôture)
            if cfg.exit_on_kalman and np.isfinite(kal[j]):
                if (side > 0 and close[j] < kal[j]) or (side < 0 and close[j] > kal[j]):
                    exit_idx, exit_px, reason = j, close[j], "clot_kalman"
                    break
        if exit_idx is None:
            exit_idx, exit_px, reason = n - 1, close[n - 1], "fin_data"

        # --- comptabilité par bougie ---
        lev_signed[i + 1: exit_idx + 1] = side * lev
        cost_frac[i] += lev * cost          # entrée
        cost_frac[exit_idx] += lev * cost   # sortie

        gross = side * (exit_px - entry) / entry
        net = gross - 2.0 * cost
        trades.append({
            "token": token, "entry_time": df.index[i], "exit_time": df.index[exit_idx],
            "side": "LONG" if side > 0 else "SHORT", "entry": entry, "sl": sl,
            "exit": exit_px, "reason": reason, "bars_held": exit_idx - i,
            "sl_dist": sl_dist, "lev": lev,
            "gross_pct": gross * 100.0, "net_pct": net * 100.0,
            "R": net / sl_dist, "pnl_frac": net * lev,
        })
        i = exit_idx        # pas de ré-entrée avant la bougie de sortie

    # Rendement par bougie du token, hors scaling portefeuille.
    px_ret = np.zeros(n)
    px_ret[1:] = close[1:] / close[:-1] - 1.0
    px_ret = np.nan_to_num(px_ret)
    bar_ret = lev_signed * px_ret - cost_frac

    tdf = pd.DataFrame(trades)
    return {
        "token": token, "trades": tdf, "index": df.index,
        "lev_signed": lev_signed, "cost_frac": cost_frac,
        "px_ret": px_ret, "bar_ret": bar_ret, "signals": s,
    }
