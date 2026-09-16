"""Critere d'evaluation : la consistance mensuelle, pas la moyenne poolee.

Lecon d'octobre 2025 : sur cette periode, un seul mois de cascade de
liquidations suffit a rendre positive n'importe quelle moyenne sur 12 mois.
Une moyenne poolee ou un t-stat sur des evenements fortement clusterises dans
le temps ne mesure donc rien d'exploitable.

On exige desormais trois choses d'un candidat :
  - moyenne MEDIANE mensuelle > cout (pas la moyenne des moyennes) ;
  - une majorite franche de mois positifs ;
  - la meme chose en OOS qu'en IS.
Un signal qui ne passe pas ces trois filtres n'est pas un signal, c'est un mois.
"""
from __future__ import annotations

import numpy as np, pandas as pd

COST = 0.0019      # taker aller-retour + slippage, hypothese de base
IS_END = "2026-03-01"


def consistency(d: pd.DataFrame, col: str, cost: float = COST) -> dict:
    """Stats robustes au clustering temporel, pour un sous-ensemble d'evenements."""
    d = d.dropna(subset=[col])
    if len(d) < 60:
        return {"n": len(d)}
    r = d[col].to_numpy()
    m = d.groupby(d["entry_time"].dt.to_period("M"))[col].mean() * 1e4
    is_, oos = d[d.entry_time < IS_END], d[d.entry_time >= IS_END]
    return {
        "n": len(d),
        "n_par_jour": len(d) / 365,
        "moy_bps": r.mean() * 1e4,
        "net_bps": (r.mean() - cost) * 1e4,
        "med_mois_bps": float(m.median()),
        "mois_pos": f"{int((m > 0).sum())}/{len(m)}",
        "mois_net_pos": f"{int((m > cost*1e4).sum())}/{len(m)}",
        "pire_mois": float(m.min()),
        "IS_bps": is_[col].mean() * 1e4 if len(is_) > 30 else np.nan,
        "OOS_bps": oos[col].mean() * 1e4 if len(oos) > 30 else np.nan,
    }


def screen(ev: pd.DataFrame, conds: dict, col: str, cost: float = COST) -> pd.DataFrame:
    rows = []
    for label, mask in conds.items():
        s = consistency(ev[mask], col, cost)
        s["filtre"] = label
        rows.append(s)
    d = pd.DataFrame(rows)
    front = ["filtre", "n", "n_par_jour", "moy_bps", "net_bps", "med_mois_bps",
             "mois_pos", "mois_net_pos", "pire_mois", "IS_bps", "OOS_bps"]
    d = d[[c for c in front if c in d.columns]]
    num = d.select_dtypes("number").columns
    d[num] = d[num].round(1)
    return d
