"""Extraction des features de flux sur tous les jours a evenements.

Un fichier de trades est telecharge UNE fois par couple (symbole, jour) et sert
a tous les evenements de ce jour, puis il est jete. Le disque ne bouge pas.
"""
import sys, time
from concurrent.futures import ThreadPoolExecutor, as_completed
import numpy as np, pandas as pd
import flow_features as ff

MIN_BURST = 0.05
ev = pd.read_parquet("events_tail24.parquet").reset_index(drop=True)
ev["signal_time"] = pd.to_datetime(ev["signal_time"])
sel = ev[ev.r_burst > MIN_BURST].copy()
sel["jour"] = sel.signal_time.dt.normalize()
groups = list(sel.groupby(["symbol", "jour"], sort=False))
print(f"{len(sel)} evenements, {len(groups)} jours-symboles", file=sys.stderr)

def work(item):
    (sym, jour), g = item
    try:
        d = ff.load_day(sym, jour)
    except Exception:
        return []
    if d is None or len(d["t"]) < 500:
        return []
    out = []
    for idx, st in zip(g.index.to_numpy(), g.signal_time):
        try:
            f = ff.features(d, st.timestamp())
        except Exception:
            f = None
        if f:
            f["_i"] = idx
            out.append(f)
    return out

# Traitement par LOTS. Soumettre les 3 798 taches d'un coup fait tenir en vol
# autant de jours de trades que l'ordonnanceur en a commences : l'OOM killer a
# tranche a la premiere tentative. Un lot a la fois borne l'empreinte.
rows, t0, n = [], time.time(), 0
LOT = 60
for k in range(0, len(groups), LOT):
    lot = groups[k:k + LOT]
    with ThreadPoolExecutor(max_workers=10) as ex:
        for fu in as_completed([ex.submit(work, it) for it in lot]):
            n += 1
            rows.extend(fu.result())
    if k % (LOT * 5) == 0:
        print(f"  {n}/{len(groups)} jours, {len(rows)} evenements "
              f"({time.time()-t0:.0f}s)", file=sys.stderr, flush=True)

fl = pd.DataFrame(rows).set_index("_i")
out = ev.join(fl, how="left")
out.to_parquet("events_flow.parquet", compression="zstd")
cov = fl.notna().mean().round(3)
print(f"\n{len(fl)} evenements avec flux ({len(fl)/len(sel)*100:.0f} % des cibles) "
      f"en {time.time()-t0:.0f}s", file=sys.stderr)
print(cov.to_string(), file=sys.stderr)
