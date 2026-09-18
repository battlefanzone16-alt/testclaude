import numpy as np, pandas as pd
from lab import data, vp_hebdo as VH, execution_limite as EL
ACTIFS=("BTCUSDT","ETHUSDT","LINKUSDT","AVAXUSDT","DOGEUSDT",
        "ADAUSDT","OPUSDT","APTUSDT","SUIUSDT","INJUSDT")
FEN=("2022-01-01","2026-08-31")
brut={}
for sym in ACTIFS:
    h1=data.load(sym,"1h","2021-10","2026-08"); m5=data.load(sym,"5m","2021-10","2026-08")
    brut[sym]=(h1, m5, VH.niveaux(h1.index, VH.profils_hebdo_jambe(m5, mode="depuis")),
               data.load_funding(sym,"2021-10","2026-08"))
print("charge", flush=True)
def pf(x):
    g=x[x>0].sum(); p=-x[x<0].sum(); return g/p if p>0 else np.nan
def agg(**kw):
    tout=[]
    for sym,(h1,m5,niv,fr) in brut.items():
        s=h1.loc[FEN[0]:FEN[1]]; nv=niv.loc[FEN[0]:FEN[1]]
        f5=m5.loc[FEN[0]:FEN[1]]
        r=EL.simuler(s,nv,fr,entree="limite",attente=12,max_barres=240,fin=f5,**kw)
        t=r.trades.copy(); t["sym"]=sym; t["R"]=t.net/t.risque; tout.append(t)
    T=pd.concat(tout, ignore_index=True)
    return {"pf":pf(T.net),"n":len(T),"espR":T.R.mean(),"risque":T.risque.median(),
            "sup1":sum(1 for _,g in T.groupby("sym") if pf(g.net)>1)}

print("\n=== chemin tranche au pas de 5 min + slippage realiste sur le stop ===", flush=True)
print(f"{'stop':>22} | {'slip 2bps':>10} {'slip 10bps':>11} {'slip 25bps':>11} {'slip 50bps':>11}", flush=True)
for nom, kw in (("25 % de l'excursion", dict(stop_mode="fraction", stop_param=0.25)),
                ("40 % de l'excursion", dict(stop_mode="fraction", stop_param=0.40)),
                ("70 % de l'excursion", dict(stop_mode="fraction", stop_param=0.70)),
                ("extreme (actuel)",    dict()),
                ("fixe 0.5 %",          dict(stop_mode="pct", stop_param=0.005)),
                ("fixe 2 %",            dict(stop_mode="pct", stop_param=0.020))):
    ligne=f"{nom:>22} |"
    for slip in (0.0002,0.0010,0.0025,0.0050):
        r=agg(slippage_stop=slip, **kw)
        ligne += f" {r['pf']:>10.3f}"
    r=agg(slippage_stop=0.0010, **kw)
    print(ligne + f"   (risque med {r['risque']*100:.2f}%, {r['n']} trades, {r['sup1']}/10)", flush=True)
