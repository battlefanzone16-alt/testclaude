import numpy as np, pandas as pd
from lab import data, vp_hebdo as VH, execution_limite as EL
ACTIFS=("BTCUSDT","ETHUSDT","LINKUSDT","AVAXUSDT","DOGEUSDT",
        "ADAUSDT","OPUSDT","APTUSDT","SUIUSDT","INJUSDT")
FEN=("2022-01-01","2026-08-31")
brut={}
for sym in ACTIFS:
    h1=data.load(sym,"1h","2021-10","2026-08"); m5=data.load(sym,"5m","2021-10","2026-08")
    brut[sym]=(h1, VH.niveaux(h1.index, VH.profils_hebdo_jambe(m5, mode="depuis")),
               data.load_funding(sym,"2021-10","2026-08"))
    print(f"  {sym} charge", flush=True)

def pf(x):
    g=x[x>0].sum(); p=-x[x<0].sum(); return g/p if p>0 else np.nan

def agg(**kw):
    tout=[]
    for sym,(h1,niv,fr) in brut.items():
        s=h1.loc[FEN[0]:FEN[1]]; nv=niv.loc[FEN[0]:FEN[1]]
        r=EL.simuler(s,nv,fr,entree="limite",attente=12,max_barres=240,**kw)
        t=r.trades.copy(); t["sym"]=sym; t["R"]=t.net/t.risque; tout.append(t)
    T=pd.concat(tout, ignore_index=True)
    cible=(T.motif=="cible").mean()
    return {"pf":pf(T.net),"n":len(T),"espR":T.R.mean(),
            "risque_med":T.risque.median(),"tx_cible":cible,
            "RR_med":(T.loc[T.motif=="cible","brut"]/T.loc[T.motif=="cible","risque"]).median(),
            "sup1":sum(1 for _,g in T.groupby("sym") if pf(g.net)>1)}

print("\n=== STOP A UNE FRACTION DE L'EXCURSION (1.0 = le stop actuel) ===", flush=True)
print(f"{'fraction':>9} | {'PF':>6} {'esp R':>8} {'risque med':>11} {'% objectif':>11} "
      f"{'RR gagnant':>11} {'trades':>7} {'actifs>1':>9}", flush=True)
for f in (0.25,0.40,0.55,0.70,0.85,1.0):
    r=agg(stop_mode="fraction", stop_param=f)
    print(f"{f:>9.2f} | {r['pf']:>6.3f} {r['espR']:>+8.4f} {r['risque_med']*100:>10.2f}% "
          f"{r['tx_cible']*100:>10.0f}% {r['RR_med']:>11.2f} {r['n']:>7} {r['sup1']:>6}/10", flush=True)

print("\n=== STOP A UN POURCENTAGE FIXE DU PRIX ===", flush=True)
print(f"{'stop':>9} | {'PF':>6} {'esp R':>8} {'% objectif':>11} {'RR gagnant':>11} "
      f"{'trades':>7} {'actifs>1':>9}", flush=True)
for p_ in (0.005,0.010,0.015,0.020,0.030,0.050):
    r=agg(stop_mode="pct", stop_param=p_)
    print(f"{p_*100:>8.1f}% | {r['pf']:>6.3f} {r['espR']:>+8.4f} {r['tx_cible']*100:>10.0f}% "
          f"{r['RR_med']:>11.2f} {r['n']:>7} {r['sup1']:>6}/10", flush=True)

print("\n=== reference : le stop actuel ===", flush=True)
r=agg()
print(f"  extreme   | PF {r['pf']:.3f}  esp {r['espR']:+.4f} R  risque med {r['risque_med']*100:.2f}%  "
      f"objectif atteint {r['tx_cible']*100:.0f}%  RR gagnant {r['RR_med']:.2f}  {r['sup1']}/10", flush=True)
