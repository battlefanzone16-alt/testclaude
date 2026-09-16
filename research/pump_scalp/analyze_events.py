"""Event study : la distribution forward conditionnelle a l'ignition.

On ne cherche pas encore une strategie. On repond a trois questions, dans
l'ordre, parce que les deux premieres peuvent tuer le projet :

  1. Apres une ignition, y a-t-il CONTINUATION ou REVERSAL ? (signe du forward)
  2. L'amplitude survit-elle au cout aller-retour (~19 bps) ?
  3. Quelles conditions separent les ignitions qui continuent de celles qui
     retombent ?
"""
from __future__ import annotations

import sys
import numpy as np, pandas as pd

pd.set_option("display.width", 200)
HZ = [5, 15, 30, 60, 120, 240]
COST = 0.0019            # 4.5 bps frais + 5 bps slippage, aller-retour


def block(ev, label, hz=HZ):
    rows = []
    for h in hz:
        r = ev[f"fwd_{h}"].dropna()
        if len(r) < 20:
            continue
        rows.append({
            "h_min": h, "n": len(r),
            "moy_bps": r.mean() * 1e4,
            "med_bps": r.median() * 1e4,
            "t_stat": r.mean() / (r.std(ddof=1) / np.sqrt(len(r))),
            "hit_%": (r > 0).mean() * 100,
            "net_bps": (r.mean() - COST) * 1e4,
            "mfe_moy_bps": ev[f"mfe_{h}"].mean() * 1e4,
            "mae_moy_bps": ev[f"mae_{h}"].mean() * 1e4,
        })
    d = pd.DataFrame(rows)
    print(f"\n--- {label}  (n={len(ev)}) ---")
    print(d.round(1).to_string(index=False))
    return d


def buckets(ev, col, edges, hz=(15, 30, 60, 120)):
    ev = ev.copy()
    ev["_b"] = pd.cut(ev[col], edges)
    rows = []
    for b, g in ev.groupby("_b", observed=True):
        row = {col: str(b), "n": len(g)}
        for h in hz:
            r = g[f"fwd_{h}"].dropna()
            row[f"fwd{h}_bps"] = r.mean() * 1e4 if len(r) > 10 else np.nan
            row[f"t{h}"] = (r.mean() / (r.std(ddof=1) / np.sqrt(len(r)))) if len(r) > 10 else np.nan
        rows.append(row)
    print(f"\n### par {col}")
    print(pd.DataFrame(rows).round(1).to_string(index=False))


def main(path="events_k5.parquet"):
    ev = pd.read_parquet(path)
    ev["entry_time"] = pd.to_datetime(ev["entry_time"])
    print(f"{len(ev)} evenements, {ev.symbol.nunique()} symboles, "
          f"{ev.entry_time.min():%Y-%m-%d} -> {ev.entry_time.max():%Y-%m-%d}")
    print(f"gap signal->entree (mediane) : {ev.gap_open.median()*1e4:.1f} bps")

    block(ev, "TOUS LES EVENEMENTS")
    for c, e in [("z_burst", [2.5, 4, 6, 9, 15, 1e9]),
                 ("vol_mult", [2, 5, 10, 25, 60, 1e9]),
                 ("taker_ratio", [0, .5, .6, .7, .8, 1.]),
                 ("break60", [-1, 0, .005, .02, .05, 1e9]),
                 ("r_60m", [-1, 0, .02, .05, .12, 1e9]),
                 ("r_burst", [0, .01, .02, .04, .08, 1e9])]:
        buckets(ev, c, e)

    # marche : le pump est-il porte par BTC ou vraiment idiosyncratique ?
    buckets(ev, "r_btc", [-1, -.002, 0, .002, 1e9])
    print("\n### correlation r_burst / r_btc :",
          round(ev[["r_burst", "r_btc"]].corr().iloc[0, 1], 3))


if __name__ == "__main__":
    main(*sys.argv[1:])
