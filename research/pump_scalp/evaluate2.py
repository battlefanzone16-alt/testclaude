"""Evaluation ponderee par EPISODE, et non par evenement.

Pourquoi ce fichier existe : le critere de consistance mensuelle d'evaluate.py
n'a pas suffi. Le signal 'grappe' passait 11/12 mois positifs et un OOS positif,
tout en ne valant rien - parce que ses 1709 evenements n'etaient que 473
episodes independants, et qu'un seul episode de 150 evenements a +822 bps
suffisait a porter la moyenne ponderee par evenement.

Un portefeuille a N slots ne prend que N positions par episode. Sa performance
suit donc la moyenne par EPISODE, pas par evenement. C'est cette moyenne qu'on
mesure ici, et c'est la seule qui soit tradable.

Un episode = des evenements separes de moins de `gap` minutes, toutes paires
confondues. On ne separe pas par symbole : quand 60 tokens s'allument dans la
meme minute, c'est un seul pari, pas soixante.
"""
from __future__ import annotations

import numpy as np, pandas as pd

COST = 0.0019
IS_END = "2026-03-01"


def episodes(t: pd.Series, gap_min: int = 60) -> pd.Series:
    """Numero d'episode pour une serie de timestamps triee."""
    d = t.sort_values()
    gap = d.diff().dt.total_seconds().fillna(1e18) / 60
    return (gap > gap_min).cumsum().reindex(t.index)


def stats(d: pd.DataFrame, col: str, cost: float = COST, gap_min: int = 60) -> dict:
    d = d.dropna(subset=[col, "entry_time"])
    if len(d) < 40:
        return {"n": len(d)}
    d = d.copy()
    d["_ep"] = episodes(d["entry_time"], gap_min)
    ep = d.groupby("_ep").agg(r=(col, "mean"), t0=("entry_time", "first"))
    r = ep["r"].to_numpy()
    se = r.std(ddof=1) / np.sqrt(len(r)) if len(r) > 1 else np.nan
    m = ep.groupby(ep.t0.dt.to_period("M"))["r"].mean() * 1e4
    is_ = ep[ep.t0 < IS_END]["r"]; oos = ep[ep.t0 >= IS_END]["r"]
    return {
        "n_ev": len(d), "n_ep": len(ep), "ev_par_ep": round(len(d)/len(ep), 1),
        "par_ev_bps": d[col].mean() * 1e4,
        "par_EP_bps": r.mean() * 1e4,
        "net_EP_bps": (r.mean() - cost) * 1e4,
        "t_EP": r.mean() / se if se and se > 0 else np.nan,
        "ep_pos_%": (r > 0).mean() * 100,
        "med_mois": float(m.median()),
        "mois_pos": f"{int((m > 0).sum())}/{len(m)}",
        "IS_EP": is_.mean() * 1e4 if len(is_) > 10 else np.nan,
        "OOS_EP": oos.mean() * 1e4 if len(oos) > 10 else np.nan,
    }


def screen(ev: pd.DataFrame, conds: dict, col: str, cost: float = COST,
           gap_min: int = 60) -> pd.DataFrame:
    rows = []
    for label, mask in conds.items():
        s = stats(ev[mask], col, cost, gap_min)
        s["filtre"] = label
        rows.append(s)
    d = pd.DataFrame(rows)
    front = ["filtre", "n_ev", "n_ep", "ev_par_ep", "par_ev_bps", "par_EP_bps",
             "net_EP_bps", "t_EP", "ep_pos_%", "med_mois", "mois_pos", "IS_EP", "OOS_EP"]
    d = d[[c for c in front if c in d.columns]]
    num = d.select_dtypes("number").columns
    d[num] = d[num].round(1)
    return d
