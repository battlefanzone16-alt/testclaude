"""La largeur de marche separe-t-elle les bons mouvements des mauvais ?

Test direct de la premisse de depart, enfin mesuree correctement : un token qui
pump SEUL (news qui lui est propre) se comporte-t-il autrement qu'un token qui
pump parce que tout l'univers pump ?
"""
import numpy as np, pandas as pd
from evaluate import screen
pd.set_option("display.width", 240)

ev = pd.read_parquet("events_k5_btc.parquet"); ev["entry_time"] = pd.to_datetime(ev["entry_time"])
br = pd.read_parquet("breadth.parquet")
ev = ev.merge(br, left_on="entry_time", right_index=True, how="left")
ev["part_univers"] = ev["breadth_z2"]
print(f"{len(ev)} evenements enrichis. Largeur au moment des ignitions :")
print(f"  mediane {ev.breadth_z2.median():.3f} contre {br.breadth_z2.median():.3f} "
      f"en temps normal -> les ignitions arrivent bien en grappes.")

base = ev.r_burst > 0.03
conds = {
    "base r_burst>3%": base,
    "SEUL : <1% de l'univers en rafale": base & (ev.breadth_z2 < 0.01),
    "SEUL+ : <0,5%": base & (ev.breadth_z2 < 0.005),
    "moyen : 1-5%": base & (ev.breadth_z2.between(0.01, 0.05)),
    "EN GRAPPE : >5% de l'univers": base & (ev.breadth_z2 > 0.05),
    "EN GRAPPE++ : >15%": base & (ev.breadth_z2 > 0.15),
    "seul ET marche calme (mkt_r5<0)": base & (ev.breadth_z2 < 0.01) & (ev.mkt_r5 < 0),
}
for h in (30, 60, 120):
    print(f"\n--- horizon {h} min ---")
    print(screen(ev, conds, f"fwd_{h}").to_string(index=False))

print("\n### Gradient de largeur, horizon 60 min (r_burst>3%)")
t = ev[base].copy()
t["_b"] = pd.qcut(t.breadth_z2, 6, duplicates="drop")
g = t.groupby("_b", observed=True)
d = pd.DataFrame({"n": g.size(), "fwd60_bps": (g.fwd_60.mean()*1e4).round(1),
                  "t": (g.fwd_60.mean()/(g.fwd_60.std()/np.sqrt(g.size()))).round(1),
                  "fwd120_bps": (g.fwd_120.mean()*1e4).round(1)})
print(d.to_string())
ev.to_parquet("events_breadth.parquet", compression="zstd")
