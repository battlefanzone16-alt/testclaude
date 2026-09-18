import numpy as np, pandas as pd
from lab import data, vp_hebdo as VH, execution_limite as EL
ACTIFS=("BTCUSDT","ETHUSDT","LINKUSDT","AVAXUSDT","DOGEUSDT",
        "ADAUSDT","OPUSDT","APTUSDT","SUIUSDT","INJUSDT")
FEN=("2022-01-01","2026-08-31")
def pf(x):
    g=x[x>0].sum(); p=-x[x<0].sum(); return g/p if p>0 else np.nan
rng=np.random.default_rng(0)
print(f"{'actif':>9} {'trades':>7} {'PF':>6} {'IC 90 %':>16} {'net taille fixe':>16} "
      f"{'net taille/risque':>18} {'DD fixe':>9} {'trim+':>7}", flush=True)
res=[]
for sym in ACTIFS:
    h1=data.load(sym,"1h","2021-10","2026-08"); m5=data.load(sym,"5m","2021-10","2026-08")
    niv=VH.niveaux(h1.index, VH.profils_hebdo_jambe(m5, mode="depuis"))
    fr=data.load_funding(sym,"2021-10","2026-08")
    s=h1.loc[FEN[0]:FEN[1]]; nv=niv.loc[FEN[0]:FEN[1]]; f5=m5.loc[FEN[0]:FEN[1]]
    r=EL.simuler(s,nv,fr,entree="limite",attente=12,max_barres=240,fin=f5,slippage_stop=0.0010)
    t=r.trades
    p=pf(t.net)
    bs=np.array([pf(pd.Series(rng.choice(t.net.to_numpy(),len(t),replace=True))) for _ in range(2000)])
    bs=bs[np.isfinite(bs)]
    # taille fixe : meme notionnel a chaque trade, levier 1, on encaisse net en %
    eq_fixe=(1+t.net.to_numpy()).cumprod()
    dd_fixe=(eq_fixe/np.maximum.accumulate(eq_fixe)-1).min()
    # taille inversement proportionnelle au risque, 0.5 % du capital par trade
    taille=(0.005/t.risque.clip(lower=0.002)).clip(upper=3.0)
    eq_r=(1+t.net.to_numpy()*taille.to_numpy()).cumprod()
    q=t.set_index("sortie").net.resample("QE").sum()
    print(f"{sym:>9} {len(t):>7} {p:>6.3f} [{np.percentile(bs,5):>5.2f};{np.percentile(bs,95):>5.2f}] "
          f"{(eq_fixe[-1]-1)*100:>+15.1f}% {(eq_r[-1]-1)*100:>+17.1f}% {dd_fixe*100:>8.0f}% "
          f"{(q>0).sum():>3}/{len(q)}", flush=True)
    res.append({"sym":sym,"pf":p,"ic_bas":np.percentile(bs,5),"net_fixe":eq_fixe[-1]-1,
                "net_risque":eq_r[-1]-1,"dd":dd_fixe,"n":len(t)})
d=pd.DataFrame(res)
print(f"\n  actifs avec PF > 1            : {(d.pf>1).sum()}/10")
print(f"  actifs dont l'IC bas depasse 1 : {(d.ic_bas>1).sum()}/10")
print(f"  actifs rentables a taille fixe : {(d.net_fixe>0).sum()}/10")
print(f"  mediane du net a taille fixe   : {d.net_fixe.median()*100:+.1f}% sur 4.7 ans")
