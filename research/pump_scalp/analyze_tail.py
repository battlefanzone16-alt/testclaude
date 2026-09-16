"""Zoom sur la queue : les vraies ignitions, pas le bruit de fond.

L'event study global dit que l'evenement median n'a pas d'edge. La structure
est dans la queue. On y regarde trois choses :
  - la forme du chemin (MFE/MAE) qui dicte stop et horizon ;
  - ce qui separe, DANS la queue, les continuations des retombees ;
  - la concentration : si 3 symboles ou 2 semaines portent tout, il n'y a rien.
"""
import sys
import numpy as np, pandas as pd
pd.set_option("display.width", 220)

HZ = [5, 15, 30, 60, 120, 240]
ev = pd.read_parquet("events_k5.parquet")
ev["entry_time"] = pd.to_datetime(ev["entry_time"])

for thr in (0.03, 0.05, 0.08):
    t = ev[ev.r_burst > thr]
    print(f"\n{'='*90}\nr_burst > {thr:.0%}   n={len(t)}  "
          f"({len(t)/365:.1f}/jour, {t.symbol.nunique()} symboles)")
    rows = []
    for h in HZ:
        r = t[f"fwd_{h}"]
        rows.append({"h": h, "moy_bps": r.mean()*1e4, "med_bps": r.median()*1e4,
                     "t": r.mean()/(r.std(ddof=1)/np.sqrt(len(r))),
                     "hit%": (r > 0).mean()*100,
                     "mfe_moy": t[f"mfe_{h}"].mean()*1e4,
                     "mfe_med": t[f"mfe_{h}"].median()*1e4,
                     "mae_moy": t[f"mae_{h}"].mean()*1e4,
                     "mae_med": t[f"mae_{h}"].median()*1e4,
                     "p90": r.quantile(.90)*1e4, "p10": r.quantile(.10)*1e4})
    print(pd.DataFrame(rows).round(0).to_string(index=False))

t = ev[ev.r_burst > 0.05].copy()
print(f"\n{'='*90}\nCONDITIONNEMENT DANS LA QUEUE (r_burst>5%, n={len(t)})")
for col, edges in [("taker_ratio", [0, .55, .65, .75, 1.]),
                   ("vol_mult", [0, 10, 25, 60, 1e9]),
                   ("z_burst", [0, 6, 10, 20, 1e9]),
                   ("r_60m", [-1, .02, .06, .15, 1e9]),
                   ("break60", [-1, 0, .01, .04, 1e9]),
                   ("r_btc", [-1, -.001, .001, 1e9]),
                   ("qv_ref_1d", [0, 3e3, 1e4, 4e4, 1e9])]:
    t["_b"] = pd.cut(t[col], edges)
    g = t.groupby("_b", observed=True)
    d = pd.DataFrame({"n": g.size()})
    for h in (30, 60, 120):
        d[f"fwd{h}"] = (g[f"fwd_{h}"].mean()*1e4).round(0)
        d[f"t{h}"] = (g[f"fwd_{h}"].mean()/(g[f"fwd_{h}"].std()/np.sqrt(g.size()))).round(1)
    print(f"\n### {col}"); print(d.to_string())

print(f"\n{'='*90}\nCONCENTRATION (r_burst>5%)")
top = t.groupby("symbol")["fwd_60"].agg(["size", "mean"]).sort_values("size", ascending=False)
print("top 12 symboles par nombre d'evenements :")
print(top.head(12).assign(mean=lambda d: (d["mean"]*1e4).round(0)).to_string())
print(f"\npart des 10 symboles les plus frequents : {top.head(10)['size'].sum()/len(t):.0%}")
tm = t.set_index("entry_time").resample("ME")["fwd_60"]
print("\npar mois :")
print(pd.DataFrame({"n": tm.size(), "fwd60_bps": (tm.mean()*1e4).round(0)}).to_string())
