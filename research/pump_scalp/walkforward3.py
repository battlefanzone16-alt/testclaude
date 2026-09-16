"""Walk-forward avec l'open interest dans la bibliotheque.

Seuils ABSOLUS et non des quantiles calcules sur toute la periode : un quantile
global est un look-ahead discret, il utilise la distribution future pour definir
le filtre d'aujourd'hui. C'est exactement le genre de fuite qui fabrique des
resultats.
"""
from __future__ import annotations

import itertools, sys
import numpy as np, pandas as pd
from evaluate2 import episodes
from walkforward2 import ep_series, run
COST = 0.0019

def build_library_oi(ev):
    lib = {}
    sess = {"tout": None, "euro": (7, 13), "us": (13, 21)}
    for rb, br, zt, oi, (sn, sv) in itertools.product(
            [0.03, 0.05], [1.0, 0.01], [3, 4], [-9.0, 0.005, 0.01, 0.02], sess.items()):
        m = (ev.r_burst > rb) & (ev.breadth_z2 < br) & (ev.z_burst > zt) & (ev.oi_chg_5m > oi)
        if sv: m &= ev.entry_time.dt.hour.between(*sv)
        lib[f"rb{rb}_br{br}_z{zt}_oi{oi}_{sn}"] = m.to_numpy()
    return lib

ev = pd.read_parquet("events_micro.parquet"); ev["entry_time"]=pd.to_datetime(ev["entry_time"])
ev["mois"]=ev.entry_time.dt.to_period("M")
lib = build_library_oi(ev)
print(f"{len(lib)} regles (dont l'open interest) x 3 horizons", file=sys.stderr)

rows, details = [], {}
for tm, me, cr, lab in [
    (6, 100, "t",       "t-stat, 100 ep min"),
    (6, 150, "t",       "t-stat, 150 ep min"),
    (6, 150, "prudent", "moyenne - 1,5 erreur-type"),
    (6, 300, "prudent", "moyenne - 1,5 ET, 300 ep min"),
    (4, 150, "prudent", "moyenne - 1,5 ET, entrainement 4 mois"),
]:
    s, d = run(ev, lib, tm, me, cr, 0.0, lab); rows.append(s); details[lab]=d
print("\n=== Walk-forward AVEC open interest ===")
print(pd.DataFrame(rows).to_string(index=False))
print("\n--- detail : 'moyenne - 1,5 erreur-type' ---")
print(details["moyenne - 1,5 erreur-type"].to_string(index=False))
