import sys, time, numpy as np, pandas as pd, bvision
ev = pd.read_parquet("events_tail24.parquet").reset_index(drop=True)
ev["entry_time"] = pd.to_datetime(ev["entry_time"])
H, n = 481, len(ev)
O = np.full((n,H), np.nan, "float32"); Hi = O.copy(); Lo = O.copy()
t0 = time.time()
for j,(sym,g) in enumerate(ev.groupby("symbol", sort=False),1):
    lo_t, hi_t = g.entry_time.min(), g.entry_time.max()
    s = (lo_t - pd.Timedelta(days=2)).strftime("%Y-%m-%d")
    e = (hi_t + pd.Timedelta(days=2)).strftime("%Y-%m-%d")
    df = bvision.fetch(sym, "1m", s, e)
    if not len(df): continue
    o=df["open"].to_numpy("float64"); h=df["high"].to_numpy("float64"); l=df["low"].to_numpy("float64")
    N=len(o); pos=df.index.get_indexer(pd.to_datetime(g["entry_time"].to_numpy()))
    for ri,i in zip(g.index.to_numpy(), pos):
        if i<0 or i>=N-2: continue
        px=o[i]
        if not np.isfinite(px) or px<=0: continue
        en=min(i+H,N); m=en-i
        O[ri,:m]=o[i:en]/px; Hi[ri,:m]=h[i:en]/px; Lo[ri,:m]=l[i:en]/px
    if j%60==0: print(f"  {j} symboles ({time.time()-t0:.0f}s)", file=sys.stderr, flush=True)
ok=np.isfinite(O[:,0])
print(f"{ok.sum()}/{n} chemins valides", file=sys.stderr)
np.savez_compressed("paths24.npz", o=O, h=Hi, l=Lo, ok=ok)
