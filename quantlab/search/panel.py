"""Moteur de backtest en panel pour la recherche à grande échelle.

Tout est causal par construction : un signal calculé sur la barre t détermine la
position DÉTENUE de t+1 à t+2, et le rendement encaissé est celui de t+1 à t+2.
Aucune information de t+1 ne sert à décider en t.
"""
from __future__ import annotations
import json, glob, os
import numpy as np
import pandas as pd

IS_A, IS_B = "2022-01-01", "2024-09-01"
OOS_A, OOS_B = "2024-09-01", "2026-09-13"
FRAIS_AR = 0.00086
SPREAD_X = 3.0


def charger(scratch: str, n_univ: int = 40):
    """Prix journaliers, funding, flux taker, et masque d'univers point-in-time."""
    toks = [t for t in json.load(open("univers_2022.json"))
            if os.path.exists(f"data_univ/{t}-4h.parquet")]
    px, hi, lo, vol, dollars, tkr, trd = {}, {}, {}, {}, {}, {}, {}
    for t in toks:
        d = pd.read_parquet(f"data_univ/{t}-4h.parquet")
        d = d[d.index < OOS_B]
        if len(d) < 2000:
            continue
        g = d.resample("D")
        px[t] = g.close.last(); hi[t] = g.high.max(); lo[t] = g.low.min()
        vol[t] = g.volume.sum(); dollars[t] = (d.volume * d.close).resample("D").sum()
        f = f"data_flow/{t}.parquet"
        if os.path.exists(f):
            x = pd.read_parquet(f); x = x[x.index < OOS_B]
            tkr[t] = x.taker_quote.resample("D").sum() / x.quote_volume.resample("D").sum().replace(0, np.nan)
            trd[t] = x.trades.resample("D").sum()
    P = pd.DataFrame(px).sort_index()
    idx = P.index
    out = dict(P=P, H=pd.DataFrame(hi).reindex(idx), L=pd.DataFrame(lo).reindex(idx),
               V=pd.DataFrame(vol).reindex(idx), D=pd.DataFrame(dollars).reindex(idx),
               TK=pd.DataFrame(tkr).reindex(idx), TR=pd.DataFrame(trd).reindex(idx))
    # funding, agrégé par jour, intervalle détecté par token
    fd = {}
    for t in P.columns:
        f = f"data_fund/{t}.parquet"
        if not os.path.exists(f):
            continue
        x = pd.read_parquet(f); x.index = pd.to_datetime(x.index).floor("h")
        x = x[~x.index.duplicated()]
        fd[t] = x.rate.resample("D").sum()
    out["F"] = pd.DataFrame(fd).reindex(idx)
    # univers point-in-time : top n_univ par volume $ sur 30 jours, reclassé mensuellement
    liq = out["D"].rolling(30, min_periods=20).mean().shift(1)
    rg = liq.rank(axis=1, ascending=False)
    prem = ~pd.Series(rg.index.to_period("M")).duplicated(keep="first").values
    rgm = rg.where(pd.Series(prem, index=rg.index), axis=0).ffill()
    out["U"] = (rgm <= n_univ) & P.notna() & P.shift(1).notna()
    # spreads
    sp = json.load(open(f"{scratch}/spreads_2022.json"))
    out["SP"] = pd.Series({t: sp.get(t, 3e-4) for t in P.columns})
    return out


def evaluer(pos: pd.DataFrame, d: dict, a: str, b: str, lag: int = 0):
    """pos = position VOULUE d'après le signal calculé à la clôture de t.

    Convention : position prise à la clôture de t, elle porte le rendement de t
    à t+1. C'est la même convention que le moteur H4 (décision à la clôture du
    signal, exécution immédiatement après) et elle n'utilise aucun prix futur :
    le signal de t ne lit que des données <= t.

    lag > 0 ajoute un retard d'exécution supplémentaire, utile comme contrôle de
    robustesse sur les signaux à horizon court.
    """
    P, U = d["P"], d["U"]
    pos = pos.where(U, 0.0).fillna(0.0)
    gross = pos.abs().sum(axis=1)
    pos = pos.div(gross.where(gross > 0, np.nan), axis=0).fillna(0.0)   # brut = 1
    held = pos.shift(lag)
    ret = P.pct_change(fill_method=None).shift(-1)                       # t -> t+1
    pnl = (held * ret).sum(axis=1)
    cout = (held.diff().abs() * (FRAIS_AR / 2 + SPREAD_X * d["SP"])).sum(axis=1)
    net = (pnl - cout).loc[a:b].iloc[:-1]
    turn = held.diff().abs().sum(axis=1).loc[a:b].mean()
    return net, turn


def stats(net: pd.Series, turn: float, lab: str = ""):
    if net.std() == 0 or len(net) < 100:
        return dict(strat=lab, sharpe=np.nan, ann=np.nan, mdd=np.nan, turn=turn)
    sh = net.mean() / net.std() * np.sqrt(365)
    eq = (1 + net).cumprod()
    tot = eq.iloc[-1] - 1
    ann = (1 + tot) ** (365 / len(net)) - 1 if 1 + tot > 0 else np.nan
    return dict(strat=lab, sharpe=sh, ann=ann, vol=net.std() * np.sqrt(365),
                mdd=(eq / eq.cummax() - 1).min(), turn=turn,
                duree=(2.0 / turn if turn > 0 else np.inf))
