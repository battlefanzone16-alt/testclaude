import numpy as np, pandas as pd
from lab import data, vp_hebdo as VH, execution_limite as EL
ACTIFS=("BTCUSDT","ETHUSDT","LINKUSDT","AVAXUSDT","DOGEUSDT",
        "ADAUSDT","OPUSDT","APTUSDT","SUIUSDT","INJUSDT")
FEN=("2022-01-01","2026-08-31")
tous=[]
for sym in ACTIFS:
    h1=data.load(sym,"1h","2021-10","2026-08"); m5=data.load(sym,"5m","2021-10","2026-08")
    niv=VH.niveaux(h1.index, VH.profils_hebdo_jambe(m5, mode="depuis"))
    fr=data.load_funding(sym,"2021-10","2026-08")
    s=h1.loc[FEN[0]:FEN[1]]; nv=niv.loc[FEN[0]:FEN[1]]; f5=m5.loc[FEN[0]:FEN[1]]
    r=EL.simuler(s,nv,fr,entree="limite",attente=12,max_barres=240,fin=f5,slippage_stop=0.0010)
    t=r.trades.copy(); t["sym"]=sym; tous.append(t)
T=pd.concat(tous, ignore_index=True).sort_values("sortie")
print(f"{len(T)} trades\n")

print("=== d'ou vient la difference entre les deux modes de taille ? ===")
T["q"]=pd.qcut(T.risque,5,labels=["stop tres serre","serre","moyen","large","tres large"])
x=T.groupby("q",observed=True).agg(n=("net","size"), risque_med=("risque","median"),
    net_moyen=("net","mean"), taille_inv=("risque", lambda r:(0.005/r.clip(lower=0.002)).clip(upper=3).mean()))
x["contribution_taille_inv"]=x.net_moyen*x.taille_inv*x.n
x["contribution_fixe"]=x.net_moyen*x.n
print(x.round(4).to_string())

def courbe(levier_notionnel, mode):
    pnl=[]
    for _,r in T.iterrows():
        if mode=="fixe": taille=levier_notionnel
        else: taille=min(0.005/max(r.risque,0.002),3.0)
        pnl.append(r.net*taille)
    p=pd.Series(pnl, index=T.sortie.to_numpy()).groupby(level=0).sum()
    eq=(1+p/len(ACTIFS)).cumprod()
    dd=(eq/eq.cummax()-1).min()
    ans=(eq.index[-1]-eq.index[0]).days/365.25
    return eq.iloc[-1]**(1/ans)-1, dd, (p.resample("QE").sum()>0).sum(), len(p.resample("QE").sum())

print("\n=== portefeuille 10 actifs : taille fixe contre taille inverse au risque ===")
print(f"{'mode':>34} | {'rendement/an':>13} {'DD max':>8} {'ratio':>6} {'trim+':>7}")
for lev in (1,2,3,5):
    a,d,q,nq=courbe(lev,"fixe")
    print(f"{'notionnel = '+str(lev)+' x capital':>34} | {a*100:>+12.1f}% {d*100:>7.0f}% "
          f"{abs(a/d):>6.2f} {q:>3}/{nq}")
a,d,q,nq=courbe(None,"inverse")
print(f"{'0.5 % de risque par trade':>34} | {a*100:>+12.1f}% {d*100:>7.0f}% {abs(a/d):>6.2f} {q:>3}/{nq}")
