"""Alignement de l'open interest : test en temps-evenement.

La correlation globale est trop bruitee pour trancher. Les ignitions, elles,
sont des sauts enormes : on peut voir a l'oeil nu dans quelle tranche l'OI
saute. On aligne donc le profil d'OI autour de la minute de signal.

Lecture :
  - si le saut d'OI apparait dans la tranche qui CONTIENT la minute de signal,
    l'horodatage est un instantane et lire cette tranche est legitime ;
  - s'il apparait dans la tranche PRECEDENTE (celle etiquetee 5 min plus tot),
    c'est que la valeur etiquetee T decrit en realite l'etat a T+5 : la lire au
    moment du signal, c'est lire le futur.
"""
import os, sys
import numpy as np, pandas as pd
from bvision import CACHE
pd.set_option("display.width", 220)

ev = pd.read_parquet("events_tail24.parquet")
ev["signal_time"] = pd.to_datetime(ev["signal_time"])
big = ev[ev.r_burst > 0.06]          # ignitions franches : le saut doit etre net
print(f"{len(big)} ignitions > 6% en 5 min\n")

OFF = list(range(-4, 5))             # tranches de 5 min autour du signal
prof = {o: [] for o in OFF}
for sym, g in big.groupby("symbol", sort=False):
    base = os.path.join(CACHE, "metrics", sym)
    if not os.path.isdir(base): continue
    fr = []
    for f in sorted(os.listdir(base)):
        try: d = pd.read_parquet(os.path.join(base, f))
        except Exception: continue
        if len(d): fr.append(d)
    if not fr: continue
    oi = pd.concat(fr).sort_index()
    oi = oi[~oi.index.duplicated(keep="last")]["oi"].astype("float64").resample("5min").last()
    for t in g.signal_time:
        b0 = t.floor("5min")         # tranche contenant la minute de signal
        try:
            vals = [oi.get(b0 + pd.Timedelta(minutes=5*o), np.nan) for o in OFF]
        except Exception:
            continue
        v = np.array(vals, dtype=float)
        if not np.isfinite(v).all() or v[0] <= 0: continue
        for i, o in enumerate(OFF):
            if i > 0 and v[i-1] > 0:
                prof[o].append(v[i]/v[i-1] - 1.0)

rows = []
for o in OFF[1:]:
    a = np.array(prof[o])
    if len(a) < 50: continue
    rows.append({"tranche": f"T{o:+d} ({o*5:+d} min)", "n": len(a),
                 "variation_OI_mediane_%": round(float(np.median(a))*100, 3),
                 "variation_OI_moyenne_%": round(float(a.mean())*100, 3)})
d = pd.DataFrame(rows)
print("Variation de l'open interest, tranche par tranche autour du signal")
print("(T+0 = la tranche de 5 min qui contient la minute de signal)")
print(d.to_string(index=False))

d.columns = ["tranche","n","med_pct","moy_pct"]
best = d.loc[d.med_pct.idxmax()]
print(f"\n-> le saut d'OI est maximal a : {best.tranche}")
