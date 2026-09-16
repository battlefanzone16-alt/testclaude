"""Hypothese C : ne pas acheter l'ignition, acheter le REPLI qui tient.

Pourquoi c'est structurellement different des tests precedents, et pas une
enieme tranche du meme tableau :
  - le prix de remplissage n'est plus la mèche mais un niveau 2 a 5% plus bas ;
  - un ordre LIMITE paie le maker (2 bps) et zero slippage a l'entree : le cout
    aller-retour tombe de ~19 a ~11 bps ;
  - on conditionne sur un evenement nouveau (le repli a eu lieu ET a tenu), pas
    sur une re-decoupe de la population d'ignition.

Le piege connu de cette famille est l'anti-selection : on n'est rempli que
quand le prix revient, c'est-a-dire precisement quand le momentum echoue. C'est
ce que le test doit trancher.
"""
from __future__ import annotations

import argparse, sys, time
import numpy as np, pandas as pd
import bvision

HZ = [15, 30, 60, 120, 240]


def run_symbol(sym, ev_sym, start, end, frac, wait, k, margin_bps=0.0):
    df = bvision.fetch(sym, "1m", start, end)
    if not len(df):
        return None
    o = df["open"].to_numpy("float64"); h = df["high"].to_numpy("float64")
    l = df["low"].to_numpy("float64");  c = df["close"].to_numpy("float64")
    N = len(o)
    pos = df.index.get_indexer(pd.to_datetime(ev_sym["signal_time"].to_numpy()))
    rows = []
    for row, t in zip(ev_sym.itertuples(), pos):
        if t < k or t + wait + max(HZ) >= N:
            continue
        L = l[t - k + 1:t + 1].min()          # point de depart de la rafale
        H = h[t - k + 1:t + 1].max()          # sommet de la rafale
        if H <= L:
            continue
        P = H - frac * (H - L)                # niveau de repli vise
        fill = -1
        for j in range(t + 1, t + 1 + wait):
            # L'ORDRE DE CES DEUX TESTS EST CRITIQUE. Un ordre limite au repos est
            # execute des que le prix touche le niveau, intra-barre, sans savoir ou
            # la barre va cloturer. Tester l'invalidation d'abord reviendrait a
            # annuler retroactivement les remplissages des barres qui cassent le
            # niveau et poursuivent leur chute -- c'est-a-dire a jeter exactement
            # la population perdante avec une information du futur.
            if l[j] <= P * (1.0 - margin_bps / 1e4):
                fill = j
                break
            if c[j] < L:                      # le mouvement est invalide : on annule
                break
        if fill < 0:
            continue
        rec = {"symbol": sym, "signal_time": df.index[t], "fill_time": df.index[fill],
               "attente_min": fill - t, "fill_px": P, "L": L, "H": H,
               "amplitude": H / L - 1.0}
        for hz in HZ:
            e = min(fill + hz, N - 1)
            rec[f"fwd_{hz}"] = o[e] / P - 1.0
            rec[f"mfe_{hz}"] = h[fill:e].max() / P - 1.0 if e > fill else np.nan
            rec[f"mae_{hz}"] = l[fill:e].min() / P - 1.0 if e > fill else np.nan
        for col in ("z_burst", "r_burst", "vol_mult", "taker_ratio", "bar_dom",
                    "up_frac", "break60", "r_60m", "r_btc", "qv_ref_1d"):
            rec[col] = getattr(row, col, np.nan)
        rows.append(rec)
    return pd.DataFrame(rows) if rows else None


_A = None
def _init(a): 
    global _A; _A = a
def _work(item):
    sym, g = item
    try:
        return run_symbol(sym, g, _A.start, _A.end, _A.frac, _A.wait, _A.k, _A.margin_bps)
    except Exception as e:
        print(f"  {sym}: {e}", file=sys.stderr); return None


def main():
    from multiprocessing import Pool
    p = argparse.ArgumentParser()
    p.add_argument("--events", default="events_k5.parquet")
    p.add_argument("--start", default="2025-09-01"); p.add_argument("--end", default="2026-09-01")
    p.add_argument("--min-burst", type=float, default=0.03)
    p.add_argument("--frac", type=float, default=0.382)
    p.add_argument("--wait", type=int, default=45)
    p.add_argument("--k", type=int, default=5)
    p.add_argument("--margin-bps", type=float, default=0.0,
                   help="le prix doit traverser la limite de tant de bps (realisme de la file)")
    p.add_argument("--workers", type=int, default=4)
    p.add_argument("--out", default="pullback.parquet")
    a = p.parse_args()

    ev = pd.read_parquet(a.events)
    ev = ev[ev.r_burst.abs() > a.min_burst].copy()
    ev["signal_time"] = pd.to_datetime(ev["signal_time"])
    print(f"{len(ev)} ignitions candidates, repli {a.frac:.0%}, attente {a.wait}min",
          file=sys.stderr)

    groups = list(ev.groupby("symbol", sort=False))
    frames, t0 = [], time.time()
    with Pool(a.workers, initializer=_init, initargs=(a,)) as pool:
        for r in pool.imap_unordered(_work, groups, chunksize=1):
            if r is not None:
                frames.append(r)
    out = pd.concat(frames, ignore_index=True).sort_values("fill_time")
    out.to_parquet(a.out, compression="zstd")
    print(f"{len(out)} remplissages ({len(out)/len(ev):.0%} des ignitions) "
          f"-> {a.out} ({time.time()-t0:.0f}s)", file=sys.stderr)


if __name__ == "__main__":
    main()
