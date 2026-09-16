"""Largeur de marche : combien de tokens bougent EN MEME TEMPS.

Le residu BTC ne suffit pas a mesurer l'idiosyncrasie. Les alts bougent souvent
ensemble sans que BTC ne bouge (rotation, risk-on sur les small caps). Un pump
vraiment propre a un token est un pump ou les 318 autres ne font rien.

Construction en O(1) memoire : on accumule des compteurs par minute au fil des
symboles plutot que de materialiser un panneau de 168 M de valeurs.
"""
from __future__ import annotations

import sys, time
import numpy as np, pandas as pd
import bvision, features

import argparse
_p = argparse.ArgumentParser()
_p.add_argument("--start", default="2025-09-01")
_p.add_argument("--end", default="2026-09-01")
_p.add_argument("--universe", default="universe.txt")
_p.add_argument("--out", default="breadth.parquet")
_A = _p.parse_args()
START, END = _A.start, _A.end
IDX = pd.date_range(START, END, freq="1min", inclusive="left")
N = len(IDX)

syms = [s.strip() for s in open(_A.universe) if s.strip()]
n_valid = np.zeros(N, dtype=np.int32)      # symboles cotes a cette minute
n_z2 = np.zeros(N, dtype=np.int32)         # dont z_5m > 2
n_z4 = np.zeros(N, dtype=np.int32)
n_up1 = np.zeros(N, dtype=np.int32)        # dont r_5m > +1%
sum_r = np.zeros(N, dtype=np.float64)      # somme des r_5m, pour la moyenne

t0 = time.time()
for i, s in enumerate(syms, 1):
    df = bvision.fetch(s, "1m", START, END)
    if len(df) < 5000:
        continue
    c = df["close"].astype("float64")
    r5 = (c / c.shift(5) - 1.0)
    sig = c.pct_change().rolling(1440, min_periods=360).std().shift(5)
    z = r5 / (sig.replace(0.0, np.nan) * np.sqrt(5))
    pos = IDX.get_indexer(df.index)
    ok = pos >= 0
    pos, r5v, zv = pos[ok], r5.to_numpy()[ok], z.to_numpy()[ok]
    fin = np.isfinite(r5v)
    np.add.at(n_valid, pos[fin], 1)
    np.add.at(sum_r, pos[fin], r5v[fin])
    np.add.at(n_up1, pos[fin & (r5v > 0.01)], 1)
    fz = np.isfinite(zv)
    np.add.at(n_z2, pos[fz & (zv > 2)], 1)
    np.add.at(n_z4, pos[fz & (zv > 4)], 1)
    if i % 50 == 0:
        print(f"  {i}/{len(syms)} ({time.time()-t0:.0f}s)", file=sys.stderr, flush=True)

v = np.maximum(n_valid, 1)
out = pd.DataFrame({
    "n_valid": n_valid,
    "breadth_z2": n_z2 / v,          # part de l'univers en rafale moderee
    "breadth_z4": n_z4 / v,          # en rafale forte
    "breadth_up1": n_up1 / v,        # part qui gagne plus de 1% sur 5 min
    "mkt_r5": sum_r / v,             # rendement 5-min moyen de l'univers
}, index=IDX)
out.index.name = "timestamp"
out.to_parquet(_A.out, compression="zstd")
print(f"-> {_A.out} ({time.time()-t0:.0f}s)", file=sys.stderr)
print(out[["breadth_z2", "breadth_z4", "breadth_up1"]].describe().round(4).to_string(),
      file=sys.stderr)
