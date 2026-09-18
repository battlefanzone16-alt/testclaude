import numpy as np, pandas as pd
from lab import data, vp_hebdo as VH, execution_limite as EL
A=("BTCUSDT","ETHUSDT","LINKUSDT","AVAXUSDT","DOGEUSDT","ADAUSDT","OPUSDT","APTUSDT","SUIUSDT","INJUSDT")
B=("LTCUSDT","ATOMUSDT","NEARUSDT","FILUSDT","ARBUSDT","TIAUSDT","SEIUSDT","DOTUSDT","ETCUSDT","AAVEUSDT")
FEN=("2022-01-01","2026-08-31")
def pf(x):
    g=x[x>0].sum(); p=-x[x<0].sum(); return g/p if p>0 else np.nan
tous=[]
for grp,nom in ((A,"initiaux"),(B,"neufs")):
    for sym in grp:
        h1=data.load(sym,"1h","2021-10","2026-08"); m5=data.load(sym,"5m","2021-10","2026-08")
        niv=VH.niveaux(h1.index, VH.profils_hebdo_jambe(m5, mode="depuis"))
        fr=data.load_funding(sym,"2021-10","2026-08")
        s=h1.loc[FEN[0]:FEN[1]]; nv=niv.loc[FEN[0]:FEN[1]]; f5=m5.loc[FEN[0]:FEN[1]]
        r=EL.simuler(s,nv,fr,entree="limite",attente=12,max_barres=240,fin=f5,slippage_stop=0.0010)
        t=r.trades.copy(); t["sym"]=sym; t["groupe"]=nom; tous.append(t)
T=pd.concat(tous, ignore_index=True)
print(f"=== {len(T)} trades, 20 actifs ===")
for nom,g in T.groupby("groupe"):
    print(f"  {nom:>9} : {len(g):>5} trades, PF {pf(g.net):.3f}")
print(f"  {'ensemble':>9} : {len(T):>5} trades, PF {pf(T.net):.3f}")

rng=np.random.default_rng(0); syms=T.sym.unique()
bs=[]
for _ in range(4000):
    tir=rng.choice(syms,len(syms),replace=True)
    bs.append(pf(pd.concat([T[T.sym==s] for s in tir], ignore_index=True).net))
bs=np.array([x for x in bs if np.isfinite(x)])
print(f"\n  IC 90 % en grappes d'actifs : [{np.percentile(bs,5):.3f} ; {np.percentile(bs,95):.3f}]")
print(f"  part des tirages > 1        : {(bs>1).mean()*100:.1f}%")

print("\n=== portefeuille 20 actifs, notionnel fixe ===")
for lev in (1,2,3):
    p=pd.Series((T.net*lev).to_numpy(), index=T.sortie.to_numpy()).groupby(level=0).sum()
    eq=(1+p/20).cumprod(); dd=(eq/eq.cummax()-1).min()
    ans=(eq.index[-1]-eq.index[0]).days/365.25
    q=p.resample("QE").sum()
    print(f"  notionnel {lev} x : {eq.iloc[-1]**(1/ans)-1:+.1%}/an  DD {dd:.0%}  "
          f"trim+ {(q>0).sum()}/{len(q)}")
print("\n=== et sur les 10 neufs seuls, en portefeuille ===")
g=T[T.groupe=="neufs"]
p=pd.Series(g.net.to_numpy(), index=g.sortie.to_numpy()).groupby(level=0).sum()
eq=(1+p/10).cumprod(); dd=(eq/eq.cummax()-1).min()
ans=(eq.index[-1]-eq.index[0]).days/365.25
q=p.resample("QE").sum()
print(f"  notionnel 1 x : {eq.iloc[-1]**(1/ans)-1:+.1%}/an  DD {dd:.0%}  trim+ {(q>0).sum()}/{len(q)}")
