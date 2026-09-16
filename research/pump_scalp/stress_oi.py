"""Le filtre 'OI explose' resiste-t-il aux memes tests qui ont tue les autres ?"""
import numpy as np, pandas as pd
from evaluate2 import episodes, stats
pd.set_option("display.width", 200)

ev = pd.read_parquet("events_micro.parquet"); ev["entry_time"]=pd.to_datetime(ev["entry_time"])
b = ev[ev.r_burst > 0.03]
thr = b.oi_chg_5m.quantile(.75)
d = b[b.oi_chg_5m > thr].dropna(subset=["fwd_120"]).copy()
d["_ep"] = episodes(d.entry_time)
ep = d.groupby("_ep").agg(r=("fwd_120","mean"), t0=("entry_time","first"), n=("fwd_120","size"))
r = ep.r.to_numpy()*100
print(f"seuil : OI +{thr*100:.2f}% sur 5 min | {len(d)} evenements, {len(ep)} episodes")
print(f"moyenne {r.mean():+.3f}%  mediane {np.median(r):+.3f}%  positifs {(r>0).mean()*100:.0f}%")
srt = np.sort(r)[::-1]
for k in (1,3,5,10,20):
    print(f"  sans les {k:>2} meilleurs episodes : {srt[k:].mean():+.3f}%  "
          f"(cout = 0,19%)")
print(f"\njours distincts : {d.entry_time.dt.normalize().nunique()}")
j = d.groupby(d.entry_time.dt.normalize()).fwd_120.mean()
print(f"part des 5 meilleurs jours dans la somme : "
      f"{j.nlargest(5).sum()/j.sum()*100:.0f} % (sur {len(j)} jours)")
m = ep.groupby(ep.t0.dt.to_period("M")).r.agg(["size","mean"])
m["bps"]=(m["mean"]*1e4).round(0); m["net"]=((m["mean"]-0.0019)*1e4).round(0)
print("\nmois par mois :"); print(m[["size","bps","net"]].to_string())
rng=np.random.default_rng(0)
bs=np.array([rng.choice(r,len(r),replace=True).mean() for _ in range(5000)])
print(f"\nbootstrap IC95 : [{np.percentile(bs,2.5):+.3f}%, {np.percentile(bs,97.5):+.3f}%]  "
      f"P(>0,19%) = {np.mean(bs>0.19)*100:.0f}%")
print(f"\nsans octobre 2025 : {ep[ep.t0.dt.to_period('M')!=pd.Period('2025-10')].r.mean()*1e4:+.1f} bps")
print(f"sans le 10 oct    : {ep[ep.t0.dt.normalize()!=pd.Timestamp('2025-10-10')].r.mean()*1e4:+.1f} bps")
