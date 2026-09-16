"""LE test critique : l'open interest est-il disponible en temps reel ?

Binance publie ses statistiques d'open interest par tranches de 5 minutes, avec
un delai de publication. Si la valeur horodatee 21:45 n'est diffusee qu'a 21:50,
alors la lire a 21:45 est un look-ahead - exactement le type de fuite qui a deja
fabrique deux faux resultats dans cette etude.

On refait donc la mesure en RETARDANT l'OI de 1 a 4 tranches de 5 minutes. Si
l'edge survit a un retard de 10-15 minutes, il ne depend pas d'une information
que le trader n'aurait pas eue. S'il s'effondre, c'etait une fuite.
"""
import sys, os, time
import numpy as np, pandas as pd
import bvision
from bvision import CACHE
pd.set_option("display.width", 200)

ev = pd.read_parquet("events_tail24.parquet")
ev["signal_time"] = pd.to_datetime(ev["signal_time"])
ev["entry_time"] = pd.to_datetime(ev["entry_time"])

LAGS = [0, 5, 10, 15, 20]
cols = {f"oi_lag{l}": np.full(len(ev), np.nan) for l in LAGS}

t0 = time.time()
for j, (sym, g) in enumerate(ev.groupby("symbol", sort=False), 1):
    base = os.path.join(CACHE, "metrics", sym)
    if not os.path.isdir(base):
        continue
    fr = []
    for f in sorted(os.listdir(base)):
        try:
            d = pd.read_parquet(os.path.join(base, f))
        except Exception:
            continue
        if len(d):
            fr.append(d)
    if not fr:
        continue
    oi = pd.concat(fr).sort_index()
    oi = oi[~oi.index.duplicated(keep="last")]["oi"].astype("float64")
    lo = g.signal_time.min() - pd.Timedelta(days=2)
    hi = g.signal_time.max() + pd.Timedelta(days=2)
    idx = pd.date_range(lo.floor("min"), hi.ceil("min"), freq="1min")
    o = oi.reindex(idx.union(oi.index)).sort_index().ffill().reindex(idx)
    t = pd.DatetimeIndex(g.signal_time)
    for l in LAGS:
        # OI retardee de l minutes : on n'utilise que ce qui etait publie a t-l
        od = o.shift(l)
        chg = (od / od.shift(5) - 1.0).reindex(t).to_numpy()
        cols[f"oi_lag{l}"][g.index.to_numpy()] = chg
    if j % 80 == 0:
        print(f"  {j} symboles ({time.time()-t0:.0f}s)", file=sys.stderr, flush=True)

for k, v in cols.items():
    ev[k] = v
ev.to_parquet("events_tail24_lag.parquet", compression="zstd")
print("couverture :", {k: f"{ev[k].notna().mean()*100:.0f}%" for k in cols}, file=sys.stderr)
