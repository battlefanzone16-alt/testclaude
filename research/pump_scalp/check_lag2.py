"""Cartographie fine de la decroissance : retards de 1 a 5 minutes.

Le premier test sautait de 0 a 5 min. Or 5 min, c'est une tranche entiere : on
change de fenetre de mesure autant qu'on ajoute du retard. Il faut savoir si
l'edge meurt a 1 minute (signal inexploitable, donc fuite) ou s'il decroit
doucement (signal reel mais exigeant en fraicheur de donnee).
"""
import sys, os, time
import numpy as np, pandas as pd
from bvision import CACHE

ev = pd.read_parquet("events_tail24.parquet")
ev["signal_time"] = pd.to_datetime(ev["signal_time"])
LAGS = [1, 2, 3, 4, 6, 8]
cols = {f"oi_lag{l}": np.full(len(ev), np.nan) for l in LAGS}
t0 = time.time()
for j, (sym, g) in enumerate(ev.groupby("symbol", sort=False), 1):
    base = os.path.join(CACHE, "metrics", sym)
    if not os.path.isdir(base): continue
    fr = []
    for f in sorted(os.listdir(base)):
        try: d = pd.read_parquet(os.path.join(base, f))
        except Exception: continue
        if len(d): fr.append(d)
    if not fr: continue
    oi = pd.concat(fr).sort_index()
    oi = oi[~oi.index.duplicated(keep="last")]["oi"].astype("float64")
    lo = g.signal_time.min() - pd.Timedelta(days=2); hi = g.signal_time.max() + pd.Timedelta(days=2)
    idx = pd.date_range(lo.floor("min"), hi.ceil("min"), freq="1min")
    o = oi.reindex(idx.union(oi.index)).sort_index().ffill().reindex(idx)
    t = pd.DatetimeIndex(g.signal_time)
    for l in LAGS:
        od = o.shift(l)
        cols[f"oi_lag{l}"][g.index.to_numpy()] = (od / od.shift(5) - 1.0).reindex(t).to_numpy()
    if j % 120 == 0: print(f"  {j} ({time.time()-t0:.0f}s)", file=sys.stderr, flush=True)
for k, v in cols.items(): ev[k] = v
ev.to_parquet("events_tail24_lag2.parquet", compression="zstd")
print("OK", file=sys.stderr)
