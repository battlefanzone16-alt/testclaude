"""Selection de l'univers de backtest.

Trois filtres, chacun pour une raison precise :

1. CRYPTO 24/7. Binance liste desormais des actions et matieres tokenisees
   (XAUUSDT, SKHYNIXUSDT, SPCXUSDT, SOXLUSDT...). Elles suivent leur sous-jacent
   et gappent a l'ouverture des bourses : leur dynamique n'a rien a voir avec un
   pump crypto sur news. On les identifie sans liste en dur, par le fait que leur
   volume du week-end s'effondre.

2. LIQUIDITE. Un scalp taker sur un carnet trop fin n'est pas executable : le
   backtest serait un fantasme. Plancher sur le volume quote median journalier.

3. HISTORIQUE MINIMAL. Il faut du warmup pour normaliser par le regime propre
   du token.

Ce qu'on ne filtre PAS : la survie. Un token deliste en cours de periode reste
dans l'univers jusqu'a sa ddernière bougie. L'exclure serait du biais du
survivant, et sur des alts a pump c'est precisement la population risquee.
"""
from __future__ import annotations

import numpy as np, pandas as pd
import bvision

START, END = "2025-09-01", "2026-09-01"
MIN_QV_MUSD = 3.0        # volume quote median journalier, en millions USD
MIN_DAYS = 90
MIN_WEEKEND = 0.40       # ratio volume week-end / semaine

sc = pd.read_csv("liquidity_screen.csv")
print(f"{len(sc)} symboles screenes")

# --- filtre 1 : crypto 24/7 -------------------------------------------------
ratios = {}
for s in sc.symbol:
    df = bvision.fetch(s, "1d", START, END)
    if len(df) < 30:
        continue
    qv, dow = df["quote_volume"], df.index.dayofweek
    we, wd = qv[dow >= 5], qv[dow < 5]
    if len(we) < 5 or len(wd) < 10 or wd.median() <= 0:
        continue
    ratios[s] = float(we.median() / wd.median())
sc["weekend_ratio"] = sc.symbol.map(ratios)

non_crypto = sc[(sc.weekend_ratio < MIN_WEEKEND) & sc.weekend_ratio.notna()]
print(f"\n{len(non_crypto)} instruments non-crypto ecartes (ratio week-end < {MIN_WEEKEND})")
print("  exemples :", ", ".join(non_crypto.nlargest(12, "qv_median_musd").symbol))

u = sc[(sc.weekend_ratio >= MIN_WEEKEND)
       & (sc.n_days >= MIN_DAYS)
       & (sc.qv_median_musd >= MIN_QV_MUSD)].copy()

print(f"\nUnivers retenu : {len(u)} symboles crypto")
print(f"  volume median journalier : "
      f"min {u.qv_median_musd.min():.1f} M$, median {u.qv_median_musd.median():.1f} M$, "
      f"max {u.qv_median_musd.max():.0f} M$")
print(f"  historique : median {u.n_days.median():.0f} jours ; "
      f"{(u.n_days < 365).sum()} symboles avec historique partiel")
deslistes = (pd.to_datetime(u['last']) < '2026-08-25').sum()
print(f"  {deslistes} symboles s'arretent avant fin aout (delistings/suspensions) : conserves")

u.sort_values("qv_median_musd", ascending=False).to_csv("universe_meta.csv", index=False)
u.symbol.sort_values().to_csv("universe.txt", index=False, header=False)
print("\n-> universe.txt")
