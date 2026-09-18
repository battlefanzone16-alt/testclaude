import itertools, numpy as np, pandas as pd
from scipy import stats
from lab import data, vp_hebdo as VH, execution_limite as EL
ACTIFS=("BTCUSDT","ETHUSDT","LINKUSDT","AVAXUSDT","DOGEUSDT",
        "ADAUSDT","OPUSDT","APTUSDT","SUIUSDT","INJUSDT")
PER={"2022-01 -> 2023-06":("2022-01-01","2023-06-30"),
     "2023-07 -> 2026-08":("2023-07-01","2026-08-31")}
brut={}
for sym in ACTIFS:
    brut[sym]=(data.load(sym,"1h","2021-10","2026-08"),
               data.load(sym,"5m","2021-10","2026-08"),
               data.load_funding(sym,"2021-10","2026-08"))
    print(f"  {sym} charge", flush=True)

def agrege(n_bins=60, part=0.70, attente=12, max_barres=240):
    tout=[]
    for sym,(h1,m5,fr) in brut.items():
        niv=VH.niveaux(h1.index, VH.profils_hebdo_jambe(m5, n_bins=n_bins, part=part, mode="depuis"))
        for nom,fen in PER.items():
            s=h1.loc[fen[0]:fen[1]]; nv=niv.loc[fen[0]:fen[1]]
            if len(s)<2000: continue
            r=EL.simuler(s,nv,fr,entree="limite",attente=attente,max_barres=max_barres)
            if r.metriques["n_trades"]<10: continue
            t=r.trades.copy(); t["R"]=t.net/t.risque; t["sym"]=sym; t["periode"]=nom
            tout.append(t)
    T=pd.concat(tout, ignore_index=True)
    g=T.loc[T.net>0,"net"].sum(); p=-T.loc[T.net<0,"net"].sum()
    t_,pv=stats.ttest_1samp(T.R.dropna(),0)
    return {"n":len(T),"pf":g/p,"espR":T.R.mean(),"brutR":(T.brut/T.risque).mean(),"p":pv,"T":T}

print("\n=== LE TEST QUI A TUE LE CYCLE 3 : sensibilite au nombre de bins ===", flush=True)
print(f"{'bins':>6} | {'PF':>6} {'esp R':>8} {'brut R':>8} {'trades':>7} {'p':>6}", flush=True)
for nb in (30,40,50,60,80,100,150):
    r=agrege(n_bins=nb)
    print(f"{nb:>6} | {r['pf']:>6.3f} {r['espR']:>+8.4f} {r['brutR']:>+8.4f} {r['n']:>7} {r['p']:>6.3f}", flush=True)

print("\n=== sensibilite a la part de volume de la value area ===", flush=True)
for part in (0.60,0.65,0.70,0.75,0.80):
    r=agrege(part=part)
    print(f"{part:>6.0%} | {r['pf']:>6.3f} {r['espR']:>+8.4f} {r['brutR']:>+8.4f} {r['n']:>7} {r['p']:>6.3f}", flush=True)

print("\n=== sensibilite a l'attente de remplissage et a la duree max ===", flush=True)
for att,mb in itertools.product((6,12,24),(72,240)):
    r=agrege(attente=att, max_barres=mb)
    print(f"att {att:>3} max {mb:>4} | {r['pf']:>6.3f} {r['espR']:>+8.4f} {r['n']:>7} {r['p']:>6.3f}", flush=True)

print("\n=== decoupage du meilleur reglage de reference (60 bins, 70 %) ===", flush=True)
r=agrege(); T=r["T"]
for cle in ("periode","sens"):
    for v,g in T.groupby(cle):
        gg=g.loc[g.net>0,"net"].sum(); pp=-g.loc[g.net<0,"net"].sum()
        print(f"  {cle}={str(v):<22} {len(g):>5} trades  PF {gg/pp:>5.3f}  esp {g.R.mean():>+7.4f} R", flush=True)
design=("BTCUSDT","ETHUSDT","LINKUSDT","AVAXUSDT","DOGEUSDT")
for nom,sel in (("conception",T.sym.isin(design)),("jamais mesures",~T.sym.isin(design))):
    g=T[sel]; gg=g.loc[g.net>0,"net"].sum(); pp=-g.loc[g.net<0,"net"].sum()
    print(f"  {nom:<24} {len(g):>5} trades  PF {gg/pp:>5.3f}  esp {g.R.mean():>+7.4f} R", flush=True)
