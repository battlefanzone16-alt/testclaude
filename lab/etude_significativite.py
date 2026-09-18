import numpy as np, pandas as pd
from lab import backtest, data, vp_hebdo as VH, execution_limite as EL
ACTIFS=("BTCUSDT","ETHUSDT","LINKUSDT","AVAXUSDT","DOGEUSDT",
        "ADAUSDT","OPUSDT","APTUSDT","SUIUSDT","INJUSDT")
FEN=("2022-01-01","2026-08-31")
tout=[]; equities={}
for sym in ACTIFS:
    h1=data.load(sym,"1h","2021-10","2026-08"); m5=data.load(sym,"5m","2021-10","2026-08")
    fr=data.load_funding(sym,"2021-10","2026-08")
    niv=VH.niveaux(h1.index, VH.profils_hebdo_jambe(m5, mode="depuis"))
    s=h1.loc[FEN[0]:FEN[1]]; nv=niv.loc[FEN[0]:FEN[1]]
    r=EL.simuler(s,nv,fr,entree="limite",attente=12,max_barres=240,risque_par_trade=0.005)
    t=r.trades.copy(); t["sym"]=sym; t["R"]=t.net/t.risque
    tout.append(t); equities[sym]=r
    print(f"  {sym:>9} {len(t):>4} trades  PF {r.metriques['pf_sans_taille']:>5.3f}  "
          f"net {r.metriques['rendement_net']*100:>+7.1f}%", flush=True)
T=pd.concat(tout, ignore_index=True)

def pf(x): 
    g=x[x>0].sum(); p=-x[x<0].sum(); return g/p if p>0 else np.nan

print(f"\n=== {len(T)} trades, 10 actifs, 2022-01 -> 2026-08 ===")
print(f"  PF global            : {pf(T.net):.3f}")
print(f"  PF shorts / longs    : {pf(T[T.sens==-1].net):.3f} / {pf(T[T.sens==1].net):.3f}")

rng=np.random.default_rng(0)
# bootstrap par grappe : on retire des ACTIFS entiers, pas des trades isoles
syms=T.sym.unique()
bs=[]
for _ in range(4000):
    tirage=rng.choice(syms,len(syms),replace=True)
    ech=pd.concat([T[T.sym==s] for s in tirage], ignore_index=True)
    bs.append(pf(ech.net))
bs=np.array([x for x in bs if np.isfinite(x)])
print(f"  IC 90 % (grappes par actif) : [{np.percentile(bs,5):.3f} ; {np.percentile(bs,95):.3f}]")
print(f"  part des tirages > 1        : {(bs>1).mean()*100:.1f}%")

bs2=np.array([pf(rng.choice(T.net.to_numpy(),len(T),replace=True)) for _ in range(4000)])
print(f"  IC 90 % (trades i.i.d.)     : [{np.percentile(bs2,5):.3f} ; {np.percentile(bs2,95):.3f}]")

print("\n=== portefeuille equipondere : les 10 actifs en parallele ===")
courbes=[]
for sym,r in equities.items():
    e=r.trades.set_index("sortie")["pnl"]
    courbes.append(e.groupby(level=0).sum())
p=pd.concat(courbes,axis=1).fillna(0.0).sum(axis=1).sort_index()
eq=(1+p/len(ACTIFS)).cumprod()
dd=eq/eq.cummax()-1
ans=(eq.index[-1]-eq.index[0]).days/365.25
print(f"  rendement total {eq.iloc[-1]-1:+.1%}  sur {ans:.1f} ans  "
      f"soit {eq.iloc[-1]**(1/ans)-1:+.1%}/an")
print(f"  drawdown max {dd.min():.1%}   trades {len(T)}   "
      f"risque 0.5 % du capital par trade")
q=p.resample("QE").sum()
print(f"  trimestres positifs : {(q>0).sum()}/{len(q)}")
