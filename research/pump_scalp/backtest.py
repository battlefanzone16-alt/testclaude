"""Backtest du scalp de pump : passe trade puis passe portefeuille.

Split temporel fixe, decide avant d'avoir vu le moindre resultat :
  IS  2025-09-01 -> 2026-03-01   (conception, choix des seuils)
  OOS 2026-03-01 -> 2026-09-01   (validation, jamais regardee pour regler)
Les pumps ARB d'aout 2026 cites par l'utilisateur tombent en OOS : c'est
volontaire, on ne veut pas calibrer sur les exemples qui ont motive l'etude.
"""
from __future__ import annotations

import argparse, sys, time
from dataclasses import replace

import numpy as np, pandas as pd

import bvision
from simulate import ExitRules, simulate_one, net_return, portfolio

IS_END = "2026-03-01"


def risk_unit(ev: pd.DataFrame, mode: str, mult: float,
              floor: float, cap: float) -> np.ndarray:
    """Distance de risque, en fraction du prix, pour chaque evenement."""
    if mode == "sigma":                 # mouvement k-min typique du token
        u = ev["sigma_ref"].to_numpy() * np.sqrt(5.0)
    elif mode == "burst":               # amplitude de la rafale elle-meme
        u = ev["r_burst"].to_numpy()
    elif mode == "pct":
        u = np.ones(len(ev))
    else:
        raise ValueError(mode)
    return np.clip(u * mult, floor, cap)


def run_trades(ev: pd.DataFrame, rules: ExitRules, risk: np.ndarray,
               start: str, end: str, quiet=True) -> pd.DataFrame:
    """Passe 1 : simule chaque evenement, symbole par symbole."""
    ev = ev.reset_index(drop=True)
    ev["_risk"] = risk
    out = []
    for sym, g in ev.groupby("symbol", sort=False):
        df = bvision.fetch(sym, "1m", start, end)
        if not len(df):
            continue
        o = df["open"].to_numpy("float64")
        h = df["high"].to_numpy("float64")
        l = df["low"].to_numpy("float64")
        pos = df.index.get_indexer(pd.to_datetime(g["entry_time"].to_numpy()))
        for row, i in zip(g.itertuples(), pos):
            if i < 0 or i >= len(o) - 2:
                continue
            xi, r, why = simulate_one(o, h, l, i, row._risk, rules)
            out.append((row.Index, sym, row.entry_time, df.index[xi],
                        xi - i, r, net_return(r, rules), why, row._risk))
    t = pd.DataFrame(out, columns=["ev", "symbol", "entry_time", "exit_time",
                                   "hold_min", "ret_brut", "ret_net", "raison", "risk"])
    return t.sort_values("entry_time").reset_index(drop=True)


def metrics(t: pd.DataFrame, label: str, capital_frac: float = 1.0) -> dict:
    """Stats par trade + courbe d'equity a taille fixe (capital_frac du capital)."""
    if not len(t):
        print(f"{label}: aucun trade")
        return {}
    r = t["ret_net"].to_numpy() * capital_frac
    eq = np.cumprod(1.0 + r)
    peak = np.maximum.accumulate(eq)
    dd = float(-(eq / peak - 1.0).min())
    wins, losses = r[r > 0], r[r < 0]
    days = max((t.exit_time.max() - t.entry_time.min()).total_seconds() / 86400, 1)
    # Sharpe par trade, annualise par la frequence reelle de trading
    per_year = len(r) / days * 365
    sr = r.mean() / r.std(ddof=1) * np.sqrt(per_year) if r.std(ddof=1) > 0 else 0.0
    m = {
        "label": label, "n": len(r),
        "trades_par_jour": len(r) / days,
        "moy_bps": r.mean() * 1e4,
        "med_bps": np.median(r) * 1e4,
        "win_%": (r > 0).mean() * 100,
        "PF": float(wins.sum() / -losses.sum()) if losses.size else np.inf,
        "equity_x": float(eq[-1]),
        "maxDD_%": dd * 100,
        "sharpe": float(sr),
        "hold_med": float(t.hold_min.median()),
        "t_stat": float(r.mean() / (r.std(ddof=1) / np.sqrt(len(r)))),
    }
    return m


def show(rows):
    d = pd.DataFrame(rows)
    num = d.select_dtypes("number").columns
    d[num] = d[num].round(2)
    print(d.to_string(index=False))
