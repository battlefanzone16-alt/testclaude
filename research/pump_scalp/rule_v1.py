"""Regle candidate, construite sur l'IS seul, puis confrontee a l'OOS.

Discipline : chaque condition est motivee economiquement AVANT de regarder son
effet, et les seuils sont ronds - pas optimises. Le but n'est pas de maximiser
l'IS mais de produire une regle qu'on puisse juger sur l'OOS sans s'etre menti.

  1. r_burst > 3%      le mouvement doit exister
  2. breadth < 1%      le token doit bouger SEUL (la premisse de depart)
  3. z > 4             et bouger fort par rapport a son propre regime
  4. r_60m < 3%        tot dans le mouvement, pas apres 15% de hausse
  5. liquide           executable
"""
import numpy as np, pandas as pd
from evaluate2 import screen, stats
pd.set_option("display.width", 250)

ev = pd.read_parquet("events_breadth.parquet"); ev["entry_time"] = pd.to_datetime(ev["entry_time"])

C = {
    "1. mouvement (r_burst>3%)":        ev.r_burst > 0.03,
    "2. seul (breadth<1%)":             ev.breadth_z2 < 0.01,
    "3. fort (z>4)":                    ev.z_burst > 4,
    "4. tot (r_60m<3%)":                ev.r_60m < 0.03,
    "5. liquide (>20k$/min)":           ev.qv_ref_1d > 20000,
}
cum, conds = pd.Series(True, index=ev.index), {}
for lab, m in C.items():
    cum = cum & m
    conds[lab] = cum.copy()

for h in (60, 120):
    print(f"\n=== horizon {h} min : effet cumulatif des conditions ===")
    print(screen(ev, conds, f"fwd_{h}").to_string(index=False))

final = cum
print(f"\n{'='*110}\nREGLE COMPLETE : {int(final.sum())} evenements")
d = ev[final]
for h in (30, 60, 120, 240):
    s = stats(d, f"fwd_{h}")
    print(f"  fwd{h:>3} : {s['n_ep']:>4} episodes | par episode {s['par_EP_bps']:>7.1f} bps "
          f"| net {s['net_EP_bps']:>7.1f} | t {s['t_EP']:>5.2f} | mois {s['mois_pos']} "
          f"| IS {s['IS_EP']:>7.1f} | OOS {s['OOS_EP']:>7.1f}")

print("\n### mois par mois (horizon 120 min, par episode)")
dd = d.dropna(subset=["fwd_120"]).copy()
from evaluate2 import episodes
dd["_ep"] = episodes(dd.entry_time)
ep = dd.groupby("_ep").agg(r=("fwd_120","mean"), t0=("entry_time","first"))
m = ep.groupby(ep.t0.dt.to_period("M")).agg(n=("r","size"), moy=("r","mean"))
m["moy_bps"] = (m.moy*1e4).round(0); m["net_bps"] = ((m.moy-0.0019)*1e4).round(0)
print(m[["n","moy_bps","net_bps"]].to_string())
