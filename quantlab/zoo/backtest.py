"""Backtest vectoriel des stratégies du zoo + statistiques de tests multiples.

Convention d'exécution (strictement causale) :
    position[i] est décidée à la CLÔTURE de la barre i à partir d'information <= i,
    et capte le rendement de la barre i+1. Les coûts sont facturés sur |Δposition|.
"""
from __future__ import annotations
import numpy as np
import pandas as pd
from scipy import stats

COST_PER_SIDE = (0.086 / 2.0 + 0.02 * 3.0) / 100.0      # 0.103% — identique au dépôt
BARS_PER_YEAR = {"1h": 24 * 365, "4h": 6 * 365, "1d": 365}


def run(df: pd.DataFrame, pos: pd.Series, tf: str, window=None, cost=COST_PER_SIDE) -> dict:
    """Rendements nets barre par barre, restreints à `window` APRÈS calcul."""
    pos = pos.reindex(df.index).fillna(0.0)
    ret = df.close.pct_change().shift(-1)                # rendement de i -> i+1
    turn = pos.diff().abs().fillna(pos.abs())
    net = pos * ret - turn * cost
    net = net.iloc[:-1]                                  # dernière barre : pas de i+1
    p = pos.iloc[:-1]
    if window is not None:
        m = (net.index >= window[0]) & (net.index <= window[1])
        net, p = net[m], p[m]
    return {"net": net.fillna(0.0), "pos": p, "tf": tf}


def stats_of(r: dict) -> dict:
    net, pos, ann = r["net"], r["pos"], BARS_PER_YEAR[r["tf"]]
    eq = (1 + net).cumprod()
    sd = net.std(ddof=1)
    sharpe = net.mean() / sd * np.sqrt(ann) if sd > 0 else 0.0
    yrs = len(net) / ann
    cagr = eq.iloc[-1] ** (1 / yrs) - 1 if yrs > 0 and eq.iloc[-1] > 0 else -1.0
    mdd = (eq / eq.cummax() - 1).min()
    # trades = segments de position constante non nulle
    blocks, cur, pnl = [], None, 0.0
    pv = pos.to_numpy(); nv = net.to_numpy()
    for i in range(len(pv)):
        if pv[i] != cur:
            if cur not in (None, 0.0): blocks.append(pnl)
            cur, pnl = pv[i], 0.0
        if pv[i] != 0.0: pnl += nv[i]
    if cur not in (None, 0.0): blocks.append(pnl)
    b = np.array(blocks) if blocks else np.array([0.0])
    gain, loss = b[b > 0].sum(), -b[b < 0].sum()
    return {"sharpe": sharpe, "cagr": cagr, "mdd": mdd, "total": eq.iloc[-1] - 1,
            "trades": len(b), "wr": float((b > 0).mean()),
            "pf": float(gain / loss) if loss > 0 else np.inf,
            "expo": float((pos != 0).mean()), "vol": float(sd * np.sqrt(ann)),
            "n_bars": len(net)}


def block_bootstrap_p(net: pd.Series, ann: int, n_iter=2000, block=None, seed=0) -> float:
    """P(Sharpe <= 0) par bootstrap stationnaire par blocs (préserve l'autocorrélation)."""
    x = net.to_numpy(); n = len(x)
    if n < 30 or x.std() == 0: return 1.0
    block = block or max(5, int(n ** (1 / 3)))
    rng = np.random.default_rng(seed)
    out = np.empty(n_iter)
    for k in range(n_iter):
        idx = []
        while len(idx) < n:
            s = rng.integers(0, n); L = rng.geometric(1 / block)
            idx.extend((s + np.arange(L)) % n)
        s_ = x[np.array(idx[:n])]
        sd = s_.std(ddof=1)
        out[k] = s_.mean() / sd * np.sqrt(ann) if sd > 0 else 0.0
    return float((out <= 0).mean())


def deflated_sharpe(sharpe, net, n_trials, ann):
    """Deflated Sharpe Ratio (Bailey & López de Prado 2014)."""
    x = net.to_numpy(); n = len(x)
    if n < 30 or n_trials < 2: return np.nan
    g, k = float(stats.skew(x)), float(stats.kurtosis(x, fisher=False))
    e = 0.5772156649
    z = stats.norm.ppf(1 - 1 / n_trials)
    z2 = stats.norm.ppf(1 - 1 / (n_trials * np.e))
    sr0 = (net.std(ddof=1) and 1.0) * ((1 - e) * z + e * z2) / np.sqrt(n)   # SR* par barre
    sr = sharpe / np.sqrt(ann)                                             # SR par barre
    den = np.sqrt(1 - g * sr + (k - 1) / 4 * sr ** 2)
    if den <= 0: return np.nan
    return float(stats.norm.cdf((sr - sr0) * np.sqrt(n - 1) / den))


def benjamini_hochberg(pvals, q=0.10):
    """Contrôle du FDR. Renvoie le masque des hypothèses retenues."""
    p = np.asarray(pvals); n = len(p)
    order = np.argsort(p); ranked = p[order]
    thr = q * (np.arange(1, n + 1)) / n
    ok = ranked <= thr
    keep = np.zeros(n, bool)
    if ok.any():
        keep[order[:np.max(np.where(ok)[0]) + 1]] = True
    return keep
