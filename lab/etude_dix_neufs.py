import numpy as np, pandas as pd
from lab import data, vp_hebdo as VH, execution_limite as EL

NEUFS=("LTCUSDT","ATOMUSDT","NEARUSDT","FILUSDT","ARBUSDT",
       "TIAUSDT","SEIUSDT","DOTUSDT","ETCUSDT","AAVEUSDT")
ANCIENS=("BTCUSDT","ETHUSDT","LINKUSDT","AVAXUSDT","DOGEUSDT",
         "ADAUSDT","OPUSDT","APTUSDT","SUIUSDT","INJUSDT")
FEN=("2022-01-01","2026-08-31")

def pf(x):
    g=x[x>0].sum(); p=-x[x<0].sum(); return g/p if p>0 else np.nan

rng=np.random.default_rng(0)

def analyse(sym):
    h1=data.load(sym,"1h","2021-10","2026-08")
    m5=data.load(sym,"5m","2021-10","2026-08")
    fr=data.load_funding(sym,"2021-10","2026-08")
    niv=VH.niveaux(h1.index, VH.profils_hebdo_jambe(m5, mode="depuis"))
    s=h1.loc[FEN[0]:FEN[1]]; nv=niv.loc[FEN[0]:FEN[1]]; f5=m5.loc[FEN[0]:FEN[1]]
    if len(s)<3000:
        return None
    r=EL.simuler(s,nv,fr,entree="limite",attente=12,max_barres=240,
                 fin=f5,slippage_stop=0.0010)
    t=r.trades
    if len(t)<60:
        return None
    p=pf(t.net)
    bs=np.array([pf(pd.Series(rng.choice(t.net.to_numpy(),len(t),replace=True)))
                 for _ in range(2000)])
    bs=bs[np.isfinite(bs)]
    eq=(1+t.net.to_numpy()).cumprod()          # notionnel fixe, sans levier
    dd=(eq/np.maximum.accumulate(eq)-1).min()
    ans=(t.sortie.iloc[-1]-t.date.iloc[0]).days/365.25
    q=t.set_index("sortie").net.resample("QE").sum()
    return {"sym":sym,"n":len(t),"pf":p,"ic_bas":np.percentile(bs,5),
            "ic_haut":np.percentile(bs,95),"net":eq[-1]-1,
            "an":(eq[-1])**(1/ans)-1 if eq[-1]>0 else -1,"dd":dd,
            "trim":f"{(q>0).sum()}/{len(q)}","annees":ans,"trades":t}

for titre, groupe in (("DIX ACTIFS NEUFS, jamais mesures", NEUFS),
                      ("les dix precedents, pour comparaison", ANCIENS)):
    print(f"\n########## {titre} ##########", flush=True)
    print(f"{'actif':>9} {'trades':>7} {'PF':>6} {'IC 90 %':>15} {'net':>9} {'/an':>8} "
          f"{'DD':>6} {'trim+':>7}", flush=True)
    res=[]
    for sym in groupe:
        try:
            a=analyse(sym)
        except Exception as e:
            print(f"{sym:>9}  indisponible ({type(e).__name__})", flush=True); continue
        if a is None:
            print(f"{sym:>9}  historique insuffisant", flush=True); continue
        res.append(a)
        print(f"{a['sym']:>9} {a['n']:>7} {a['pf']:>6.3f} "
              f"[{a['ic_bas']:>5.2f};{a['ic_haut']:>5.2f}] {a['net']*100:>+8.1f}% "
              f"{a['an']*100:>+7.1f}% {a['dd']*100:>5.0f}% {a['trim']:>7}", flush=True)
    if res:
        d=pd.DataFrame([{k:v for k,v in r.items() if k!="trades"} for r in res])
        print(f"  --> PF > 1 : {(d.pf>1).sum()}/{len(d)}   "
              f"IC bas > 1 : {(d.ic_bas>1).sum()}/{len(d)}   "
              f"rentables : {(d.net>0).sum()}/{len(d)}   "
              f"PF median {d.pf.median():.3f}   net median {d.net.median()*100:+.1f}%", flush=True)
        if groupe is NEUFS:
            T=pd.concat([r["trades"] for r in res], ignore_index=True)
            print(f"  --> agregat des neufs : {len(T)} trades, PF {pf(T.net):.3f}", flush=True)
