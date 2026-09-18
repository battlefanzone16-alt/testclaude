import numpy as np, pandas as pd
from lab import data, vp_hebdo as VH, execution_limite as EL
from lab.costs import CoutsHL
ACTIFS=("BTCUSDT","ETHUSDT","LINKUSDT","AVAXUSDT","DOGEUSDT",
        "ADAUSDT","OPUSDT","APTUSDT","SUIUSDT","INJUSDT")
FEN=("2022-01-01","2026-08-31")
brut={}
for sym in ACTIFS:
    h1=data.load(sym,"1h","2021-10","2026-08"); m5=data.load(sym,"5m","2021-10","2026-08")
    brut[sym]=(h1, VH.niveaux(h1.index, VH.profils_hebdo_jambe(m5, mode="depuis")),
               data.load_funding(sym,"2021-10","2026-08"))
def pf(x):
    g=x[x>0].sum(); p=-x[x<0].sum(); return g/p if p>0 else np.nan
def agg(**kw):
    tout=[]; fills=[]
    for sym,(h1,niv,fr) in brut.items():
        s=h1.loc[FEN[0]:FEN[1]]; nv=niv.loc[FEN[0]:FEN[1]]
        r=EL.simuler(s,nv,fr,entree="limite",attente=12,max_barres=240,**kw)
        t=r.trades.copy(); t["sym"]=sym; tout.append(t); fills.append(r.metriques["taux_remplissage"])
    T=pd.concat(tout, ignore_index=True)
    return T, pf(T.net), np.median(fills)

print("=== file d'attente : il faut TRAVERSER le niveau pour etre servi ===")
print(f"{'marge exigee':>14} | {'PF':>6} {'trades':>7} {'fill':>6} {'actifs>1':>9}")
for m in (0.0, 0.0002, 0.0005, 0.0010, 0.0020):
    T,p_,f=agg(marge_fill=m)
    sup=sum(1 for s,g in T.groupby("sym") if pf(g.net)>1)
    print(f"{m*100:>13.2f}% | {p_:>6.3f} {len(T):>7} {f*100:>5.0f}% {sup:>6}/10")

print("\n=== et si le fill maker etait une illusion ? (entree facturee en taker) ===")
for nom, c in (("maker 1.5 bps", CoutsHL()),
               ("taker a l'entree", CoutsHL(maker=0.00045))):
    T,p_,f=agg(couts=c)
    print(f"  {nom:>18} : PF {p_:.3f}")

print("\n=== pire cas cumule : traverser de 5 bps ET payer taker partout ===")
T,p_,f=agg(marge_fill=0.0005, couts=CoutsHL(maker=0.00065))
print(f"  PF {p_:.3f}  sur {len(T)} trades, fill {f*100:.0f}%")
