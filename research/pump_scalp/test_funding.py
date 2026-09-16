"""Cout de funding : ce que je n'avais pas paye.

Les positions vont jusqu'a 6 heures et le funding tombe toutes les 8 heures
(00:00, 08:00, 16:00 UTC). Une partie des trades traverse donc un reglement. Un
long paie quand le taux est positif - et pendant un pump, il l'est presque
toujours, parfois violemment. C'est un cout reel que le backtest ignorait.
"""
import os, sys
import numpy as np, pandas as pd
from bvision import CACHE
pd.set_option("display.width", 200)

ev = pd.read_parquet("events_tail24.parquet"); ev["entry_time"] = pd.to_datetime(ev["entry_time"])
sel = ev[ev.r_burst > 0.03]
print(f"{len(sel)} evenements")

rows = []
for sym, g in sel.groupby("symbol", sort=False):
    base = os.path.join(CACHE, "funding", sym)
    if not os.path.isdir(base): continue
    fr = []
    for f in sorted(os.listdir(base)):
        try: d = pd.read_parquet(os.path.join(base, f))
        except Exception: continue
        if len(d): fr.append(d)
    if not fr: continue
    fu = pd.concat(fr).sort_index()
    fu = fu[~fu.index.duplicated(keep="last")]["taux"].astype("float64")
    for t in g.entry_time:
        # prochain reglement de funding apres l'entree
        nxt = fu.index[fu.index > t]
        if not len(nxt): continue
        dt = (nxt[0] - t).total_seconds() / 60
        rows.append({"minutes_avant_funding": dt, "taux": float(fu.loc[nxt[0]])})
d = pd.DataFrame(rows)
print(f"\ntaux de funding au prochain reglement apres l'entree ({len(d)} trades) :")
print(f"  median {d.taux.median()*100:.4f} %  moyen {d.taux.mean()*100:.4f} %  "
      f"p90 {d.taux.quantile(.9)*100:.4f} %  p99 {d.taux.quantile(.99)*100:.4f} %")
print(f"  part des taux positifs (le long paie) : {(d.taux>0).mean()*100:.0f} %")

print("\nPart des trades traversant un reglement, et cout moyen, par duree de detention :")
out = []
for hold in (60, 120, 240, 360):
    cross = d.minutes_avant_funding <= hold
    cost = np.where(cross, d.taux, 0.0)
    out.append({"duree_min": hold,
                "part_traversant_%": round(cross.mean()*100, 1),
                "cout_funding_moyen_bps": round(cost.mean()*1e4, 2),
                "cout_si_traverse_bps": round(d.taux[cross].mean()*1e4, 2) if cross.any() else 0})
print(pd.DataFrame(out).to_string(index=False))
print("\nA comparer au peage aller-retour de 19 bps : le funding est un cout")
print("de second ordre ici, mais il n'est pas nul et va toujours contre le long.")
