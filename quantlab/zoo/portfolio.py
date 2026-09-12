"""Agrégation portefeuille multi-tokens — la seule échelle où le Sharpe a un sens.

Construction standard de la littérature suiveuse de tendance (Moskowitz-Ooi-
Pedersen) : chaque token est dimensionné à volatilité cible constante, de sorte
que chacun contribue le même risque. Tout est causal — la volatilité de
dimensionnement à la barre i n'utilise que des rendements <= i-1.
"""
from __future__ import annotations
import numpy as np
import pandas as pd

COST_PER_SIDE = (0.086 / 2.0 + 0.02 * 3.0) / 100.0
BARS_PER_YEAR = {"1h": 24 * 365, "4h": 6 * 365}


def load_panel(paths: dict, tf: str) -> dict:
    """Aligne tous les tokens sur un index commun. NaN = token non listé."""
    fr = {k: pd.read_parquet(v) for k, v in paths.items()}
    idx = sorted(set().union(*[f.index for f in fr.values()]))
    idx = pd.DatetimeIndex(idx)
    out = {c: pd.DataFrame({k: f[c].reindex(idx) for k, f in fr.items()}) for c in
           ("open", "high", "low", "close")}
    out["index"], out["tf"] = idx, tf
    return out


def positions(panel, fn) -> pd.DataFrame:
    """Applique une stratégie à chaque token. NaN là où le token n'existe pas."""
    cols = {}
    for t in panel["close"].columns:
        d = pd.DataFrame({c: panel[c][t] for c in ("open", "high", "low", "close")}).dropna()
        if len(d) < 250:
            cols[t] = pd.Series(np.nan, index=panel["index"]); continue
        cols[t] = fn(d).reindex(panel["index"])
    return pd.DataFrame(cols)


def portfolio_returns(panel, pos: pd.DataFrame, vol_target=0.20, vol_win=60,
                      max_lev_token=3.0, cost=COST_PER_SIDE, gross_cap=1.0):
    """Rendements nets du portefeuille, barre par barre.

    u_i = pos_i * min(vol_cible / vol_i, plafond)  puis normalisation du brut.
    La position décidée en i capte le rendement de i+1 ; coûts sur |Δu|.
    """
    ann = BARS_PER_YEAR[panel["tf"]]
    close = panel["close"]
    ret = close.pct_change()
    # volatilité causale : rendements jusqu'à i-1 seulement
    vol = ret.shift(1).rolling(vol_win, min_periods=vol_win // 2).std() * np.sqrt(ann)
    lev = (vol_target / vol).clip(upper=max_lev_token)
    u = (pos * lev).where(pos.notna() & vol.notna(), 0.0).fillna(0.0)
    # 1) parité de risque : brut normalisé à gross_cap (contributions égales)
    gross = u.abs().sum(axis=1)
    u = u.div(gross.replace(0.0, np.nan), axis=0).fillna(0.0) * gross_cap

    # 2) ciblage de volatilité AU NIVEAU PORTEFEUILLE, causal.
    #    Sans cette étape la normalisation du brut absorbe tout le dimensionnement
    #    par token et la vol réalisée dérive librement (37% pour une cible de 20%).
    raw = (u * ret.shift(-1).fillna(0.0)).sum(axis=1)
    pvol = raw.shift(1).rolling(vol_win, min_periods=vol_win // 2).std() * np.sqrt(ann)
    k = (vol_target / pvol).clip(upper=max_lev_token).replace([np.inf, -np.inf], np.nan).fillna(0.0)
    u = u.mul(k, axis=0)

    fwd = ret.shift(-1).fillna(0.0)
    pnl = (u * fwd).sum(axis=1)
    turn = u.diff().abs().sum(axis=1).fillna(u.abs().sum(axis=1))
    net = (pnl - turn * cost).iloc[:-1]
    return {"net": net, "gross": u.abs().sum(axis=1).iloc[:-1],
            "nnet": u.sum(axis=1).iloc[:-1], "tf": panel["tf"]}


def stats(r, window=None) -> dict:
    net = r["net"]; ann = BARS_PER_YEAR[r["tf"]]
    g, nn = r["gross"], r["nnet"]
    if window is not None:
        m = (net.index >= window[0]) & (net.index <= window[1])
        net, g, nn = net[m], g[m], nn[m]
    eq = (1 + net).cumprod(); sd = net.std(ddof=1)
    yrs = len(net) / ann
    return {"sharpe": float(net.mean() / sd * np.sqrt(ann)) if sd > 0 else 0.0,
            "cagr": float(eq.iloc[-1] ** (1 / yrs) - 1) if yrs > 0 and eq.iloc[-1] > 0 else -1.0,
            "mdd": float((eq / eq.cummax() - 1).min()), "total": float(eq.iloc[-1] - 1),
            "vol": float(sd * np.sqrt(ann)), "gross": float(g.mean()),
            "net_expo": float(nn.mean()), "n_bars": int(len(net))}
