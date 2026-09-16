"""Datation exacte de l'instantane d'open interest.

Astuce decisive : le fichier metrics contient l'OI en contrats ET en dollars.
Leur rapport est le PRIX au moment exact du releve. On peut donc comparer ce
prix implicite aux klines 1 minute, dont l'horodatage est connu sans ambiguite,
et lire directement a quelle minute le releve a ete pris.

C'est exact, pas statistique : si le releve etiquete 21:45 est bien pris a
21:45, le prix implicite colle au close de 21:45 et a aucun autre.
"""
import os, sys
import numpy as np, pandas as pd
import bvision
from bvision import CACHE
pd.set_option("display.width", 200)

res = {}
for sym in ["BTCUSDT", "ETHUSDT", "SOLUSDT", "ARBUSDT", "DOGEUSDT", "ZECUSDT"]:
    base = os.path.join(CACHE, "metrics", sym)
    if not os.path.isdir(base):
        continue
    fr = []
    for f in sorted(os.listdir(base))[:40]:
        try:
            d = pd.read_parquet(os.path.join(base, f))
        except Exception:
            continue
        if len(d) and "oi_value" in d.columns:
            fr.append(d)
    if not fr:
        continue
    m = pd.concat(fr).sort_index()
    m = m[~m.index.duplicated(keep="last")]
    m = m[(m["oi"] > 0) & (m["oi_value"] > 0)]
    implied = (m["oi_value"].astype("float64") / m["oi"].astype("float64"))

    px = bvision.fetch(sym, "1m", str(m.index.min().date()),
                       str((m.index.max() + pd.Timedelta(days=1)).date()))
    if not len(px):
        continue
    c = px["close"].astype("float64")

    row = {}
    for off in range(-6, 7):                 # decalage teste, en minutes
        cc = c.shift(-off).reindex(implied.index)
        j = implied.index[np.isfinite(cc.to_numpy()) & np.isfinite(implied.to_numpy())]
        if len(j) < 500:
            continue
        # erreur relative mediane entre prix implicite et close decale
        err = np.abs(implied.loc[j].to_numpy() / cc.loc[j].to_numpy() - 1.0)
        row[off] = float(np.median(err)) * 1e4          # en bps
    res[sym] = row

d = pd.DataFrame(res).round(2)
d.index.name = "decalage_min"
print("Ecart median entre le prix implicite (oi_value/oi) et le close de la kline")
print("decalee de k minutes, en bps. Le minimum date l'instantane.\n")
print(d.to_string())
moy = d.mean(axis=1)
best = moy.idxmin()
print(f"\nmoyenne sur les symboles : minimum a k = {best} min "
      f"({moy.loc[best]:.2f} bps d'ecart)")
print(f"  a k=0 : {moy.get(0, float('nan')):.2f} bps")
print(f"  a k=+5 : {moy.get(5, float('nan')):.2f} bps")
print(f"\n-> l'OI etiquetee T est relevee a T{best:+d} min.")
if best == 0:
    print("   Lire la tranche T au moment du signal est donc LEGITIME :")
    print("   c'est une photo prise a T, pas la fin d'une fenetre.")
