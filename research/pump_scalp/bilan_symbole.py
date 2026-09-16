"""Le meme detecteur, sur un symbole, sur toute la periode.

A quoi ca sert : une belle journee ne prouve rien. Ce script met en regard la
journee qu'on a en tete et les ~1400 autres declenchements de l'annee sur le
meme token. C'est la seule facon de voir si le detecteur separe quoi que ce
soit, ou s'il produit surtout du bruit ponctue de quelques beaux jours.
"""
import sys
import numpy as np, pandas as pd
pd.set_option("display.width", 200)
COST = 0.19          # aller-retour taker + slippage, en %

sym = sys.argv[1] if len(sys.argv) > 1 else "ARBUSDT"
ev = pd.read_parquet("events_k5.parquet")
ev["entry_time"] = pd.to_datetime(ev["entry_time"])
a = ev[ev.symbol == sym].copy()
if not len(a):
    sys.exit(f"{sym} absent du fichier d'evenements")
a["jour"] = a.entry_time.dt.normalize()

print(f"{sym} : {len(a)} entrees sur {a.jour.nunique()} jours "
      f"({len(a)/a.jour.nunique():.1f} par jour)\n")
for h, lab in [(60, "+1h"), (120, "+2h"), (240, "+4h")]:
    r = a[f"fwd_{h}"] * 100
    print(f"  {lab} : moyenne {r.mean():+.2f}%  mediane {r.median():+.2f}%  "
          f"gagnants {(r>0).mean()*100:.0f}%  |  net de {COST}% : {r.mean()-COST:+.2f}%")

j = a.groupby("jour")["fwd_120"].agg(["size", "mean"])
j["mean"] = (j["mean"] * 100).round(2)
print("\nLes 5 meilleures journees (moyenne a +2h) :"); print(j.nlargest(5, "mean").to_string())
print("\nLes 5 pires :"); print(j.nsmallest(5, "mean").to_string())

tot = a.fwd_120.sum()
top = j.nlargest(5, "mean").index
n_top = a.jour.isin(top).sum()
print(f"\nSomme des rendements a +2h sur la periode : {tot*100:.0f} points")
print(f"  les 5 meilleures journees en apportent {a[a.jour.isin(top)].fwd_120.sum()*100:+.0f}, "
      f"pour {n_top} entrees sur {len(a)} ({n_top/len(a)*100:.1f} %).")
print("\nAutrement dit : le detecteur trouve bien les beaux jours. Il les noie")
print("simplement dans un flot d'entrees qui ne rapportent rien, et rien dans les")
print("features ne permet de les distinguer a l'avance (cf. ml_search.py).")
