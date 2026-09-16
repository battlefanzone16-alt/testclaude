"""Le pump-regime : k=30 min, avec les features qui separent regime et meche."""
import numpy as np, pandas as pd
from evaluate import screen, consistency
pd.set_option("display.width", 250)

ev = pd.read_parquet("events_k30.parquet")
ev["entry_time"] = pd.to_datetime(ev["entry_time"])
print(f"{len(ev)} evenements k=30, {ev.symbol.nunique()} symboles")
print(f"bar_dom median {ev.bar_dom.median():.2f} | up_frac median {ev.up_frac.median():.2f}")

base = ev.r_burst > 0.05
print("\n### LONG a 60 min, effet de chaque filtre ajoute a r_burst>5% (k=30)")
conds = {
    "r_burst>5% (base)": base,
    "  + regime, pas meche (bar_dom<0.4)": base & (ev.bar_dom < 0.40),
    "  + majorite de barres hausse (up_frac>0.55)": base & (ev.up_frac > 0.55),
    "  + les deux": base & (ev.bar_dom < 0.40) & (ev.up_frac > 0.55),
    "  + les deux + cassure 240m": base & (ev.bar_dom < 0.40) & (ev.up_frac > 0.55) & (ev.break240 > 0),
    "  + les deux + flux taker acheteur": base & (ev.bar_dom < 0.40) & (ev.up_frac > 0.55) & (ev.taker_ratio > 0.55),
    "  + les deux + volume persistant": base & (ev.bar_dom < 0.40) & (ev.up_frac > 0.55) & (ev.vol_persist > 3),
    "MECHE au contraire (bar_dom>0.6)": base & (ev.bar_dom > 0.60),
}
for h in (30, 60, 120):
    print(f"\n-- horizon {h} min --")
    print(screen(ev, conds, f"fwd_{h}").to_string(index=False))
