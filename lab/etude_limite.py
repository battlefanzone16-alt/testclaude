"""Etude de l'entree en ordre limite sur le VP hebdomadaire fixe.

Reproduit les trois mesures qui concluent le cycle 5 :
  - le profit factor par actif et par periode ;
  - le test du mecanisme suppose (le PF suit-il la largeur de la value area ?) ;
  - l'agregat de tous les trades, seul chiffre qui ait une puissance statistique.

Les cinq premiers actifs ont servi a la conception, les cinq suivants n'avaient
jamais ete mesures dans ce depot au moment de l'etude.
"""
import numpy as np, pandas as pd
from scipy import stats
from lab import data, vp_hebdo as VH, execution_limite as EL
ACTIFS=("BTCUSDT","ETHUSDT","LINKUSDT","AVAXUSDT","DOGEUSDT",
        "ADAUSDT","OPUSDT","APTUSDT","SUIUSDT","INJUSDT")
PER={"2022-01 -> 2023-06":("2022-01-01","2023-06-30"),
     "2023-07 -> 2026-08":("2023-07-01","2026-08-31")}
lignes=[]; tous_trades=[]
for sym in ACTIFS:
    h1=data.load(sym,"1h","2021-10","2026-08"); m5=data.load(sym,"5m","2021-10","2026-08")
    niv=VH.niveaux(h1.index, VH.profils_hebdo(m5)); fr=data.load_funding(sym,"2021-10","2026-08")
    for nom,fen in PER.items():
        s=h1.loc[fen[0]:fen[1]]; nv=niv.loc[fen[0]:fen[1]]
        if len(s)<2000: continue
        r=EL.simuler(s,nv,fr,entree="limite",attente=12,max_barres=240)
        if r.metriques["n_trades"]<10: continue
        largeur=((nv.vah-nv.val)/s.close).median()
        vol=s.close.pct_change().std()*np.sqrt(24*365)
        t=r.trades.copy(); t["sym"]=sym; t["periode"]=nom; tous_trades.append(t)
        lignes.append({"sym":sym,"periode":nom,"pf":r.metriques["pf_sans_taille"],
                       "largeur_VA":largeur,"vol":vol,"n":r.metriques["n_trades"],
                       "cout_en_R":0.0006/t.risque.median(),
                       "esp_R":(t.net/t.risque).mean()})
d=pd.DataFrame(lignes)
print("=== le PF suit-il la largeur de la value area ? ===")
print(d.sort_values("largeur_VA")[["sym","periode","largeur_VA","vol","cout_en_R","pf","esp_R","n"]]
      .round(3).to_string(index=False))
for x in ("largeur_VA","vol","cout_en_R"):
    rho,p = stats.spearmanr(d[x], d.pf)
    print(f"\ncorrelation de rang {x:>12} vs PF : rho {rho:+.2f}  p={p:.3f}")

T=pd.concat(tous_trades, ignore_index=True)
T["R"]=T.net/T.risque
print(f"\n=== agregat des {len(T)} trades, tous actifs, toutes periodes ===")
g=T.loc[T.net>0,"net"].sum(); pr=-T.loc[T.net<0,"net"].sum()
print(f"  profit factor global : {g/pr:.3f}")
print(f"  esperance par trade  : {T.R.mean():+.4f} R   (ecart-type {T.R.std():.2f})")
t_,p_=stats.ttest_1samp(T.R.dropna(),0)
print(f"  test contre zero     : t={t_:+.2f}  p={p_:.3f}")
print(f"  frais moyens         : {T.frais.mean()*100:.3f}% du notionnel par trade "
      f"= {(T.frais/T.risque).mean():.3f} R")
print(f"  brut par trade       : {(T.brut/T.risque).mean():+.4f} R")
