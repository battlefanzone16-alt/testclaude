"""La sortie passive resiste-t-elle a l'exigence de traversee ?"""
import sys, time
from concurrent.futures import ThreadPoolExecutor, as_completed
import numpy as np, pandas as pd
import flow_features as ff, tick_engine as te
N_JOURS, SEED, LAT, T = 2500, 7, 2.0, 10_000
MARGES = [0, 5, 10, 20]
CFG = [(40,900),(40,300),(80,900)]
uni = sorted({s.strip() for s in open("universe_union.txt") if s.strip()})
rng = np.random.default_rng(SEED)
jours = pd.date_range("2024-09-01","2026-08-30",freq="D")
pairs = list({(uni[i],jours[j]) for i,j in zip(rng.integers(0,len(uni),N_JOURS*2),
                                               rng.integers(0,len(jours),N_JOURS*2))})[:N_JOURS]
def work(pj):
    sym,jour=pj
    try: d=ff.load_day(sym,jour)
    except Exception: return []
    if d is None or len(d["t"])<5000: return []
    t,px,q,sell=d["t"],d["px"],d["q"],d["sell"]; qv=px*q
    try:
        grid,sig,vps,tps=te.baseline(t,px,qv)
        sigs=te.detect(t,px,qv,sell,W=30.0,z_min=6.0,vol_mult=8.0,cooldown=900.0,
                       grid=grid,sig=sig,vps=vps,tps=tps)
    except Exception: return []
    out=[]
    for i in sigs:
        base={"symbol":sym,"ts":float(t[i])}
        for tp,h in CFG:
            for mg in MARGES:
                r=te.trade_mixte(t,px,qv,sell,i,LAT*1000,T,max_hold_s=h,
                                 trail_pct=0.015,stop_pct=0.015,tp_pct=tp/1e4,
                                 marge_bps=mg)
                if r:
                    k=f"{tp}_{h}_{mg}"
                    base[f"pnl_{k}"]=r[0]; base[f"why_{k}"]=r[2]
        out.append(base)
    return out
rows,t0,n=[],time.time(),0
for k in range(0,len(pairs),60):
    with ThreadPoolExecutor(max_workers=10) as ex:
        for fu in as_completed([ex.submit(work,p) for p in pairs[k:k+60]]):
            n+=1; rows.extend(fu.result())
    if k%360==0: print(f"  {n}/{len(pairs)} ({time.time()-t0:.0f}s)",file=sys.stderr,flush=True)
pd.DataFrame(rows).to_parquet("tick_marge.parquet",compression="zstd")
print(f"\n{len(rows)} declenchements en {time.time()-t0:.0f}s",file=sys.stderr)
