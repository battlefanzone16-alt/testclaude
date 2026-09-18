import numpy as np, pandas as pd
from scipy import stats
from lab import data, vp_hebdo as VH, execution_limite as EL
A=("BTCUSDT","ETHUSDT","LINKUSDT","AVAXUSDT","DOGEUSDT","ADAUSDT","OPUSDT","APTUSDT","SUIUSDT","INJUSDT")
B=("LTCUSDT","ATOMUSDT","NEARUSDT","FILUSDT","ARBUSDT","TIAUSDT","SEIUSDT","DOTUSDT","ETCUSDT","AAVEUSDT")
FEN=("2022-01-01","2026-08-31")
def pf(x):
    g=x[x>0].sum(); p=-x[x<0].sum(); return g/p if p>0 else np.nan

cache={}
def charge(sym):
    if sym not in cache:
        h1=data.load(sym,"1h","2021-10","2026-08"); m5=data.load(sym,"5m","2021-10","2026-08")
        cache[sym]=(h1,m5,data.load_funding(sym,"2021-10","2026-08"))
    return cache[sym]

def mesure(sym, mode):
    h1,m5,fr=charge(sym)
    niv=VH.niveaux(h1.index, VH.profils_hebdo_jambe(m5, mode=mode) if mode!="semaine"
                   else VH.profils_hebdo(m5))
    s=h1.loc[FEN[0]:FEN[1]]; nv=niv.loc[FEN[0]:FEN[1]]; f5=m5.loc[FEN[0]:FEN[1]]
    r=EL.simuler(s,nv,fr,entree="limite",attente=12,max_barres=240,fin=f5,slippage_stop=0.0010)
    t=r.trades.copy(); t["sym"]=sym; return t

print("### TEST A — le classement des trois ancrages tient-il sur les actifs neufs ?", flush=True)
print("   (si l'ancrage gagnant change, le choix du cycle 6 etait du bruit)\n", flush=True)
print(f"{'ancrage':>16} | {'PF 10 initiaux':>15} {'PF 10 neufs':>13} {'ecart':>8}", flush=True)
resultats={}
for mode,nom in (("semaine","semaine entiere"),("jambe","jambe bas->haut"),("depuis","depuis extreme")):
    lignes={}
    for grp,g in (("A",A),("B",B)):
        T=pd.concat([mesure(s,mode) for s in g], ignore_index=True)
        lignes[grp]=(pf(T.net), T)
    resultats[nom]=lignes
    print(f"{nom:>16} | {lignes['A'][0]:>15.3f} {lignes['B'][0]:>13.3f} "
          f"{lignes['B'][0]-lignes['A'][0]:>+8.3f}", flush=True)

print("\n### TEST B — la deterioration suit-elle la tendance de l'actif ?", flush=True)
print("   (une regle de retour a la moyenne saigne sur un actif qui derive)\n", flush=True)
rows=[]
for grp,g in (("initiaux",A),("neufs",B)):
    for sym in g:
        h1,_,_=charge(sym)
        s=h1.loc[FEN[0]:FEN[1]]
        T=resultats["depuis extreme"]["A" if grp=="initiaux" else "B"][1]
        t=T[T.sym==sym]
        if len(t)<60: continue
        r=s.close.pct_change()
        derive=(s.close.iloc[-1]/s.close.iloc[0])**(365/((s.index[-1]-s.index[0]).days))-1
        vol=r.std()*np.sqrt(24*365)
        # part du temps ou le prix est sous sa moyenne longue : mesure de derive baissiere
        sous=(s.close < s.close.rolling(24*30).mean()).mean()
        rows.append({"groupe":grp,"sym":sym,"pf":pf(t.net),
                     "derive_an":derive,"vol":vol,"sous_moyenne":sous,
                     "pf_long":pf(t[t.sens==1].net),"pf_short":pf(t[t.sens==-1].net),
                     "n":len(t)})
d=pd.DataFrame(rows)
print(d.sort_values("derive_an")[["groupe","sym","derive_an","vol","sous_moyenne",
                                  "pf","pf_long","pf_short","n"]].round(3).to_string(index=False))
for x in ("derive_an","vol","sous_moyenne"):
    rho,p_=stats.spearmanr(d[x], d.pf)
    print(f"\n  correlation de rang {x:>14} vs PF : rho {rho:+.2f}  p={p_:.3f}")
print("\n  moyennes par groupe :")
print(d.groupby("groupe")[["derive_an","vol","sous_moyenne","pf","pf_long","pf_short"]].mean().round(3).to_string())
d.to_csv("lab_out/diagnostic_deterioration.csv", index=False)
