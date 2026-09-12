"""White Reality Check : « le meilleur des N stratégies bat-il le hasard ? »

On rééchantillonne le MARCHÉ par blocs de bougies entières (la géométrie
intrabar et le clustering de volatilité sont préservés, les coïncidences de
dates sont détruites), on rejoue TOUT le zoo sur chaque chemin, et on collecte
le Sharpe MAXIMUM. La distribution obtenue est celle du meilleur résultat
qu'on obtiendrait en testant autant de stratégies sur un marché sans edge.
"""
from __future__ import annotations
import numpy as np
import pandas as pd


def resample_path(d: pd.DataFrame, rng, block=30) -> pd.DataFrame:
    """Bootstrap stationnaire par blocs de bougies entières."""
    c = d.close.to_numpy(float)
    ret = np.empty(len(c)); ret[0] = 0.0; ret[1:] = c[1:] / c[:-1] - 1.0
    ro = d.open.to_numpy() / c; rh = d.high.to_numpy() / c; rl = d.low.to_numpy() / c

    n = len(c); idx = []
    while len(idx) < n:
        s = rng.integers(0, n); L = max(1, rng.geometric(1.0 / block))
        idx.extend((s + np.arange(L)) % n)
    idx = np.array(idx[:n])

    nc = c[0] * np.cumprod(1.0 + ret[idx])
    out = pd.DataFrame({"open": nc * ro[idx], "high": nc * rh[idx],
                        "low": nc * rl[idx], "close": nc}, index=d.index)
    out["high"] = out[["open", "high", "low", "close"]].max(axis=1)
    out["low"] = out[["open", "high", "low", "close"]].min(axis=1)
    return out


def null_max_sharpe(d, zoo, tf, n_meas, n_paths=500, seed=0, progress=None):
    """Distribution du Sharpe max (et de tous les Sharpe) sous l'hypothèse nulle."""
    from .backtest import run, stats_of
    rng = np.random.default_rng(seed)
    maxima, allsh = [], []
    for k in range(n_paths):
        p = resample_path(d, rng)
        sh = []
        for fn in zoo.values():
            try:
                r = run(p, fn(p), tf)
                r["net"] = r["net"].iloc[-n_meas:]; r["pos"] = r["pos"].iloc[-n_meas:]
                sh.append(stats_of(r)["sharpe"])
            except Exception:
                sh.append(np.nan)
        sh = np.array(sh, float)
        maxima.append(np.nanmax(sh)); allsh.append(sh)
        if progress and (k + 1) % progress == 0:
            print(f"    {k+1}/{n_paths}  max median {np.median(maxima):+.2f}", flush=True)
    return np.array(maxima), np.vstack(allsh)
