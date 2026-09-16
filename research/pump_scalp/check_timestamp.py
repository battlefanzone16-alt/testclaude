"""L'horodatage de l'open interest : instantane a T, ou fin de fenetre ?

C'est la question factuelle dont depend tout le resultat. Si sum_open_interest
horodate 21:45 est un INSTANTANE a 21:45, le lire a 21:47 est legitime. Si c'est
l'etat a la fin d'une fenetre 21:45-21:50, alors le lire a 21:47 utilise le
futur, et mon 'retard 0' est une fuite de 3 minutes en moyenne.

Test empirique, sans dependre de la documentation : l'open interest et le prix
bougent ensemble (les nouvelles positions se prennent quand le prix bouge). On
mesure donc la correlation entre la variation d'OI de la tranche T et la
variation de prix de chaque tranche voisine. Le pic de correlation dit ou se
situe reellement l'information.
"""
import os, sys
import numpy as np, pandas as pd
import bvision
from bvision import CACHE
pd.set_option("display.width", 200)

syms = [s.strip() for s in open("universe.txt") if s.strip()][:60]
acc = {k: [] for k in range(-3, 4)}
n_ok = 0
for sym in syms:
    base = os.path.join(CACHE, "metrics", sym)
    if not os.path.isdir(base): continue
    fr = []
    for f in sorted(os.listdir(base))[:60]:
        try: d = pd.read_parquet(os.path.join(base, f))
        except Exception: continue
        if len(d): fr.append(d)
    if len(fr) < 5: continue
    oi = pd.concat(fr).sort_index()
    oi = oi[~oi.index.duplicated(keep="last")]["oi"].astype("float64")
    oi = oi.resample("5min").last()
    px = bvision.fetch(sym, "1m", str(oi.index.min().date()),
                       str((oi.index.max()+pd.Timedelta(days=1)).date()))
    if not len(px): continue
    c = px["close"].astype("float64").resample("5min").last()
    j = oi.index.intersection(c.index)
    if len(j) < 500: continue
    d_oi = (oi.loc[j].pct_change()).to_numpy()
    d_px = (c.loc[j].pct_change().abs()).to_numpy()      # amplitude du mouvement
    for k in acc:
        a, b = d_oi, np.roll(d_px, -k)
        m = np.isfinite(a) & np.isfinite(b)
        if m.sum() > 300:
            acc[k].append(np.corrcoef(a[m], b[m])[0, 1])
    n_ok += 1

print(f"{n_ok} symboles analyses\n")
print("Correlation |variation OI tranche T| avec |variation prix tranche T+k|")
print("(k=0 : meme tranche. Un pic a k=0 => horodatage instantane, lecture legitime.)")
rows = [{"k (tranches de 5 min)": k, "decalage_min": k*5,
         "correlation_moyenne": round(float(np.mean(v)), 4), "n_symboles": len(v)}
        for k, v in sorted(acc.items()) if v]
d = pd.DataFrame(rows)
print(d.to_string(index=False))
best = d.loc[d.correlation_moyenne.idxmax()]
print(f"\n-> pic de correlation a k = {int(best['k (tranches de 5 min)'])} "
      f"({int(best['decalage_min'])} min)")
