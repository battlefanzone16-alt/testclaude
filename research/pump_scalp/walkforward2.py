"""Walk-forward, avec des politiques de selection serieuses.

La v1 choisissait la regle a la plus forte moyenne brute sur 40 episodes : c'est
une machine a selectionner du bruit. Avant de conclure, on teste des criteres
qu'un praticien utiliserait vraiment - t-stat plutot que moyenne, exigence
d'echantillon, fenetre d'entrainement plus longue, et une politique qui ne trade
que si la meilleure regle depasse nettement le cout.
"""
from __future__ import annotations

import itertools, sys
import numpy as np, pandas as pd
from evaluate2 import episodes
from walkforward import build_library, COST

def ep_series(ev, mask, col, mmask):
    d = ev[mask & mmask].dropna(subset=[col])
    if len(d) < 5:
        return np.array([])
    return d.assign(_ep=episodes(d.entry_time)).groupby("_ep")[col].mean().to_numpy()

def run(ev, lib, train_m, min_ep, critere, seuil_bps=0.0, label=""):
    mois = sorted(ev.mois.unique()); horizons = ["fwd_60", "fwd_120", "fwd_240"]
    res = []
    for i in range(train_m, len(mois)):
        tm = mois[i]
        tr = ev.mois.isin(mois[i-train_m:i]).to_numpy(); te = (ev.mois == tm).to_numpy()
        best, score = None, -np.inf
        for name, m in lib.items():
            for h in horizons:
                r = ep_series(ev, m, h, tr)
                if len(r) < min_ep: continue
                if critere == "moyenne": s = r.mean()
                elif critere == "t":     s = r.mean()/(r.std(ddof=1)/np.sqrt(len(r)))
                else:                    s = r.mean() - 1.5*r.std(ddof=1)/np.sqrt(len(r))
                if s > score: best, score, bm = (name, h), s, r.mean()
        if best is None: continue
        if bm*1e4 < seuil_bps:            # on ne trade pas si l'edge estime est faible
            res.append({"mois": str(tm), "regle": "PAS DE TRADE", "IS_bps": round(bm*1e4,1),
                        "n_ep": 0, "OOS_net_bps": 0.0}); continue
        name, h = best
        r = ep_series(ev, lib[name], h, te)
        res.append({"mois": str(tm), "regle": f"{name[:34]} {h}", "IS_bps": round(bm*1e4,1),
                    "n_ep": len(r),
                    "OOS_net_bps": round((r.mean()-COST)*1e4,1) if len(r) else np.nan})
    d = pd.DataFrame(res); v = d.OOS_net_bps.dropna()
    return {"politique": label, "mois_testes": len(v), "OOS_moy_bps": round(v.mean(),1),
            "OOS_med_bps": round(v.median(),1), "mois_pos": f"{int((v>0).sum())}/{len(v)}",
            "IS_moy_bps": round(d.IS_bps.mean(),1)}, d

ev = pd.read_parquet("events_breadth.parquet"); ev["entry_time"]=pd.to_datetime(ev["entry_time"])
ev["mois"]=ev.entry_time.dt.to_period("M")
lib = build_library(ev)
rows=[]
for tm, me, cr, sl, lab in [
    (6, 40,  "moyenne", 0,  "v1 naive : moyenne, 40 ep min"),
    (6, 150, "moyenne", 0,  "moyenne, 150 episodes min"),
    (6, 150, "t",       0,  "t-stat, 150 ep min"),
    (6, 300, "t",       0,  "t-stat, 300 ep min"),
    (4, 150, "t",       0,  "t-stat, 150 ep, entrainement 4 mois"),
    (6, 150, "prudent", 0,  "moyenne - 1,5 erreur-type"),
    (6, 150, "t",      40,  "t-stat + ne trader que si edge>40bps"),
]:
    s, d = run(ev, lib, tm, me, cr, sl, lab); rows.append(s)
    if cr=="t" and me==150 and tm==6 and sl==0:
        print("\n--- detail de la politique 't-stat, 150 ep min' ---")
        print(d.to_string(index=False))
print("\n=== Comparaison des politiques de selection ===")
print(pd.DataFrame(rows).to_string(index=False))
