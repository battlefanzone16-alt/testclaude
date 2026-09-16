"""Extraction des evenements d'ignition + surface de rendements forward.

Un "evenement" = la premiere minute ou le token depasse simultanement un seuil
d'amplitude normalisee et un seuil d'expansion de volume. Le seuil est pris
LARGE a ce stade : le but de l'event study n'est pas de selectionner, c'est de
mesurer la distribution conditionnelle pour que le choix des seuils vienne
ensuite des donnees et non d'une intuition.

Anti-double-comptage : apres un evenement, le symbole est mis en sourdine
COOLDOWN minutes. Sans ca un seul pump de 40 minutes produit 40 "evenements"
quasi identiques et toutes les statistiques deviennent du bruit correle.
"""
from __future__ import annotations

import argparse, os, sys, time
import numpy as np, pandas as pd

import bvision, features

HORIZONS = [1, 3, 5, 10, 15, 30, 60, 120, 240]


def dedupe(flags: np.ndarray, cooldown: int) -> np.ndarray:
    """Positions des evenements retenus : greedy, premier arrive premier servi."""
    idx = np.flatnonzero(flags)
    keep, last = [], -10**9
    for i in idx:
        if i - last >= cooldown:
            keep.append(i)
            last = i
    return np.array(keep, dtype=np.int64)


def events_for_symbol(sym, start, end, k, z_min, vol_min, cooldown,
                      min_qv_1d, warmup_bars, btc_close, direction="up"):
    df = bvision.fetch(sym, "1m", start, end)
    if len(df) < warmup_bars + 500:
        return None

    f = features.add_features(df, k=k, btc_close=btc_close)
    n = len(df)

    ok = (
        (f["z_burst"].to_numpy() >= z_min)
        & (f["vol_mult"].to_numpy() >= vol_min)
        & (f["qv_ref_1d"].to_numpy() >= min_qv_1d)
        & (f["r_burst"].to_numpy() > 0)
    ) if direction == "up" else (
        (f["z_burst"].to_numpy() <= -z_min)
        & (f["vol_mult"].to_numpy() >= vol_min)
        & (f["qv_ref_1d"].to_numpy() >= min_qv_1d)
        & (f["r_burst"].to_numpy() < 0)
    )
    ok &= np.isfinite(f["z_burst"].to_numpy()) & np.isfinite(f["vol_mult"].to_numpy())
    ok[:warmup_bars] = False
    ok[n - 2:] = False                      # besoin d'au moins la barre d'entree

    sig = dedupe(ok, cooldown)
    if sig.size == 0:
        return None

    entry = sig + 1                          # execution a l'ouverture de t+1
    ev = pd.DataFrame({
        "symbol": sym,
        "signal_time": df.index[sig],
        "entry_time": df.index[entry],
        "signal_pos": sig,
        "entry_px": df["open"].to_numpy()[entry],
    })
    for col in ("z_burst", "r_burst", "vol_mult", "taker_ratio", "r_btc",
                "r_resid", "break60", "r_60m", "r_240m", "qv_ref_1d",
                "qv_burst", "trades_burst", "sigma_ref",
                "bar_dom", "up_frac", "vol_persist", "break240",
                "dist_hh1d", "r_1d"):
        ev[col] = f[col].to_numpy()[sig]
    # gap d'execution : ce qu'on paie deja entre le signal et l'ouverture suivante
    ev["gap_open"] = df["open"].to_numpy()[entry] / df["close"].to_numpy()[sig] - 1.0

    for name, arr in features.forward_paths(df, entry, HORIZONS).items():
        ev[name] = arr
    return ev


_BTC = None
_ARGS = None


def _init(start, end, args):
    global _BTC, _ARGS
    _BTC = bvision.fetch("BTCUSDT", "1m", start, end)["close"]
    _ARGS = args


def _work(sym):
    a = _ARGS
    try:
        ev = events_for_symbol(sym, a.start, a.end, a.k, a.z_min, a.vol_min,
                               a.cooldown, a.min_qv_1d, a.warmup, _BTC, a.direction)
    except Exception as e:
        print(f"  {sym}: ECHEC {e}", file=sys.stderr)
        return None
    return ev


def main():
    from multiprocessing import Pool
    p = argparse.ArgumentParser()
    p.add_argument("--universe", default="universe.txt")
    p.add_argument("--start", default="2025-09-01")
    p.add_argument("--end", default="2026-09-01")
    p.add_argument("--k", type=int, default=5)
    p.add_argument("--z-min", type=float, default=2.5)
    p.add_argument("--vol-min", type=float, default=2.0)
    p.add_argument("--cooldown", type=int, default=60)
    p.add_argument("--min-qv-1d", type=float, default=2000.0,
                   help="volume quote median par minute, en USD")
    p.add_argument("--warmup", type=int, default=4320, help="barres ignorees au debut (3j)")
    p.add_argument("--direction", default="up", choices=["up", "down"])
    p.add_argument("--workers", type=int, default=8)
    p.add_argument("--out", default="events_k5.parquet")
    a = p.parse_args()

    syms = [s.strip() for s in open(a.universe) if s.strip()]
    print(f"{len(syms)} symboles, k={a.k}, z>={a.z_min}, vol>={a.vol_min}, "
          f"cooldown={a.cooldown}min", file=sys.stderr)

    frames, t0, n = [], time.time(), 0
    with Pool(a.workers, initializer=_init, initargs=(a.start, a.end, a)) as pool:
        for ev in pool.imap_unordered(_work, syms, chunksize=1):
            n += 1
            if ev is not None:
                frames.append(ev)
            if n % 40 == 0:
                tot = sum(len(f) for f in frames)
                print(f"  {n}/{len(syms)} symboles, {tot} evenements "
                      f"({time.time()-t0:.0f}s)", file=sys.stderr, flush=True)

    out = pd.concat(frames, ignore_index=True).sort_values("entry_time")
    out.to_parquet(a.out, compression="zstd")
    print(f"\n{len(out)} evenements -> {a.out} ({time.time()-t0:.0f}s)", file=sys.stderr)


if __name__ == "__main__":
    main()
