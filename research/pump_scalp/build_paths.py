"""Precalcul des chemins de prix post-entree, normalises par le prix d'entree.

Motivation : chaque backtest relit sinon 319 symboles x 1 an de 1-min, soit
plusieurs minutes par jeu de parametres. Impossible de balayer quoi que ce soit.
On extrait donc une fois pour toutes, pour chaque evenement, les H barres qui
suivent l'entree, en RELATIF (divisees par le prix d'entree). Les regles de
sortie ne dependant que de ratios, cela ne perd aucune information et tient en
memoire en float32.

Les barres manquantes (fin d'historique) sont NaN : le simulateur s'arrete
dessus plutot que d'inventer un prix.
"""
from __future__ import annotations

import argparse, sys, time
import numpy as np, pandas as pd
import bvision


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--events", default="events_k5.parquet")
    p.add_argument("--start", default="2025-09-01")
    p.add_argument("--end", default="2026-09-01")
    p.add_argument("--horizon", type=int, default=481)
    p.add_argument("--out", default="paths_k5.npz")
    a = p.parse_args()

    ev = pd.read_parquet(a.events).reset_index(drop=True)
    H = a.horizon
    n = len(ev)
    O = np.full((n, H), np.nan, dtype=np.float32)
    Hi = np.full((n, H), np.nan, dtype=np.float32)
    Lo = np.full((n, H), np.nan, dtype=np.float32)

    t0 = time.time()
    for j, (sym, g) in enumerate(ev.groupby("symbol", sort=False), 1):
        df = bvision.fetch(sym, "1m", a.start, a.end)
        if not len(df):
            continue
        o = df["open"].to_numpy("float64")
        h = df["high"].to_numpy("float64")
        l = df["low"].to_numpy("float64")
        N = len(o)
        pos = df.index.get_indexer(pd.to_datetime(g["entry_time"].to_numpy()))
        for row_i, i in zip(g.index.to_numpy(), pos):
            if i < 0 or i >= N - 2:
                continue
            e = min(i + H, N)
            px = o[i]
            if not np.isfinite(px) or px <= 0:
                continue
            m = e - i
            O[row_i, :m] = o[i:e] / px
            Hi[row_i, :m] = h[i:e] / px
            Lo[row_i, :m] = l[i:e] / px
        if j % 40 == 0:
            print(f"  {j} symboles ({time.time()-t0:.0f}s)", file=sys.stderr, flush=True)

    ok = np.isfinite(O[:, 0])
    print(f"{ok.sum()}/{n} evenements avec chemin valide", file=sys.stderr)
    np.savez_compressed(a.out, o=O, h=Hi, l=Lo, ok=ok)
    print(f"-> {a.out} ({time.time()-t0:.0f}s)", file=sys.stderr)


if __name__ == "__main__":
    main()
