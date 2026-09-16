"""Le flux d'ordres separe-t-il les bons mouvements des mauvais ?

Derniere source disponible, et la seule immunisee au biais qui a tue l'open
interest : les aggTrades sont horodates a la milliseconde, il n'y a rien a
supposer sur leur alignement.

Hypotheses posees AVANT le test, avec leur direction attendue :
  F1  desequilibre agressif a l'achat eleve = vraie pression acheteuse -> continue
  F2  gros ordres dominants et acheteurs = flux institutionnel        -> continue
  F3  un seul print geant = coup isole, pas de suite                  -> retombe
  F4  fort impact par unite de volume = carnet fin, mouvement factice -> retombe
  F5  arrivee des ordres qui accelere en fin de rafale                -> continue
  F6  flux reparti sur la duree plutot qu'en a-coups                  -> continue

Evaluation : ponderation par episode, deux periodes independantes, et retrait
des trois meilleurs mois. Les trois filtres qui ont elimine tous les candidats
precedents.
"""
import numpy as np, pandas as pd
from evaluate2 import screen, stats
pd.set_option("display.width", 255)

ev = pd.read_parquet("events_flow.parquet"); ev["entry_time"] = pd.to_datetime(ev["entry_time"])
FL = ["ofi","ofi_ecart","big_part","big_ofi","trade_max_part","taille_moy_rel",
      "taux_rel","taux_fin","vol_fin_part","px_fin_part","impact","secondes_actives"]
b = ev[ev.r_burst > 0.05].dropna(subset=["ofi"])
print(f"{len(b)} evenements avec flux, "
      f"{b.entry_time.min():%Y-%m} -> {b.entry_time.max():%Y-%m}\n")
print(b[FL].describe().loc[["mean","50%","std"]].round(3).to_string())

q = lambda c,p: b[c].quantile(p)
m = lambda c: ev[c]
conds = {
    "base (r_burst>5%, flux dispo)": ev.index.isin(b.index),
    "F1 flux acheteur (ofi top 25%)":   ev.index.isin(b.index) & (m("ofi") > q("ofi",.75)),
    "F1' flux vendeur (ofi bas 25%)":   ev.index.isin(b.index) & (m("ofi") < q("ofi",.25)),
    "F2 gros ordres acheteurs":         ev.index.isin(b.index) & (m("big_part") > q("big_part",.60)) & (m("big_ofi") > 0.1),
    "F3 un seul print domine (top 25%)":ev.index.isin(b.index) & (m("trade_max_part") > q("trade_max_part",.75)),
    "F3' flux distribue (bas 25%)":     ev.index.isin(b.index) & (m("trade_max_part") < q("trade_max_part",.25)),
    "F4 fort impact (carnet fin)":      ev.index.isin(b.index) & (m("impact") > q("impact",.75)),
    "F4' faible impact (carnet epais)": ev.index.isin(b.index) & (m("impact") < q("impact",.25)),
    "F5 arrivee qui accelere":          ev.index.isin(b.index) & (m("taux_fin") > q("taux_fin",.75)),
    "F6 flux reparti (top 25%)":        ev.index.isin(b.index) & (m("secondes_actives") > q("secondes_actives",.75)),
}
for h in (60, 120):
    print(f"\n=== horizon {h} min, par episode, cout 19 bps ===")
    d = screen(ev, conds, f"fwd_{h}")
    print(d.to_string(index=False))
    ok = d[(d.IS_EP > 0) & (d.OOS_EP > 0) & (d.net_EP_bps > 0)]
    print(f"  -> {len(ok)}/{len(d)} filtres nets positifs avec IS et OOS positifs")

print("\n### Gradients par quintile (fwd 120, par episode)")
for c in ["ofi","big_ofi","trade_max_part","impact","taux_fin","secondes_actives"]:
    t = b.dropna(subset=[c,"fwd_120"]).copy()
    if len(t) < 500: continue
    t["_q"] = pd.qcut(t[c], 5, labels=False, duplicates="drop")
    rows=[]
    for k,g in t.groupby("_q"):
        s = stats(g, "fwd_120")
        rows.append({"q":int(k)+1,"n_ep":s.get("n_ep"),"bps":round(s.get("par_EP_bps",np.nan),1),
                     "t":round(s.get("t_EP",np.nan),2),"IS":round(s.get("IS_EP",np.nan),0),
                     "OOS":round(s.get("OOS_EP",np.nan),0)})
    print(f"\n-- {c} --"); print(pd.DataFrame(rows).to_string(index=False))
