"""La piste journaliere, verifiee proprement.

Le premier run excluait par accident les 30 premiers jours de cotation de chaque
token : le filtre `volmult` exige une mediane glissante sur 30 jours, donc les
lignes sans historique tombaient silencieusement. Ce n'etait pas un choix, c'etait
un effet de bord - et il porte le signe de la moyenne. On refait donc la mesure
avec l'exclusion rendue EXPLICITE et parametrable, pour montrer la sensibilite au
lieu de la subir.
"""
import numpy as np, pandas as pd, bvision
pd.set_option("display.width", 200)

syms = [s.strip() for s in open("universe.txt") if s.strip()]
rows = []
for s in syms:
    df = bvision.fetch(s, "1d", "2025-09-01", "2026-09-01")
    if len(df) < 60:
        continue
    c = df["close"].astype("float64"); o = df["open"].astype("float64")
    sig = pd.DataFrame({"symbol": s, "date": df.index,
                        "r1": (c / c.shift(1) - 1).to_numpy(),
                        "age_j": np.arange(len(df))})
    for h in (3, 5, 10):
        sig[f"fwd_{h}"] = (o.shift(-1 - h) / o.shift(-1) - 1).to_numpy()
    rows.append(sig)
d = pd.concat(rows, ignore_index=True)
d["date"] = pd.to_datetime(d["date"])
p = d[d.r1 > 0.15].dropna(subset=["fwd_10"])

print("Apres un pump journalier > +15%, rendement du token les 10 jours suivants")
print("(un short gagne l'oppose ; l'age est le nombre de jours depuis le debut de l'historique)\n")
out = []
for lab, sub in [("tout (aucune exclusion)", p),
                 ("age >= 30 j (le run initial)", p[p.age_j >= 30]),
                 ("age >= 60 j", p[p.age_j >= 60]),
                 ("age < 30 j (les jeunes listings seuls)", p[p.age_j < 30])]:
    r = sub["fwd_10"]
    m = sub.groupby(sub.date.dt.to_period("M"))["fwd_10"].mean()
    out.append({"population": lab, "n": len(r), "moy_%": r.mean()*100,
                "med_%": r.median()*100,
                "t": r.mean()/(r.std(ddof=1)/np.sqrt(len(r))),
                "mois_neg": f"{(m<0).sum()}/{len(m)}",
                "p95_%": r.quantile(.95)*100, "max_%": r.max()*100})
t = pd.DataFrame(out); t[t.select_dtypes("number").columns] = t.select_dtypes("number").round(2)
print(t.to_string(index=False))

print("\n-> La MEDIANE est stable (~-11%) dans toutes les populations.")
print("   La MOYENNE bascule de signe selon qu'on inclut ou non les jeunes listings :")
print("   ce sont eux qui portent la queue droite. Un short median gagne, un short")
print("   en esperance ne gagne que si on exclut une population - ce qui n'est pas")
print("   un edge, c'est un choix d'univers.")
