"""Hypothese B : ne pas acheter l'ignition, la VENDRE.

Le tableau global montre fwd15 = -86 bps (t=-7.7, n=5736) pour vol_mult 25-60x.
Avant de s'exciter, trois pieges a eliminer :
  1. le gap signal->entree : si le retour en arriere a deja eu lieu a l'ouverture
     suivante, l'edge est un mirage d'echantillonnage ;
  2. la concentration temporelle (le piege d'octobre 2025) ;
  3. le risque : shorter une bougie verticale, c'est la MAE qui decide.
"""
import numpy as np, pandas as pd
pd.set_option("display.width", 240)

ev = pd.read_parquet("events_k5_btc.parquet")
ev["entry_time"] = pd.to_datetime(ev["entry_time"])
ev["mois"] = ev.entry_time.dt.to_period("M")
ev["IS"] = ev.entry_time < "2026-03-01"

print("=== 1. GAP signal->entree par bucket de vol_mult (le piege n1) ===")
ev["_v"] = pd.cut(ev.vol_mult, [2, 5, 10, 25, 60, 1e9])
g = ev.groupby("_v", observed=True)
print(pd.DataFrame({
    "n": g.size(),
    "gap_med_bps": (g.gap_open.median()*1e4).round(1),
    "gap_moy_bps": (g.gap_open.mean()*1e4).round(1),
    "r_burst_med%": (g.r_burst.median()*100).round(2),
}).to_string())

print("\n=== 2. SHORT : rendement (= -fwd) par bucket, IS vs OOS ===")
rows = []
for b, d in ev.groupby("_v", observed=True):
    for per, dd in (("IS", d[d.IS]), ("OOS", d[~d.IS]), ("hors oct25", d[d.mois != "2025-10"])):
        r = -dd["fwd_15"].dropna()
        if len(r) < 50: continue
        rows.append({"vol_mult": str(b), "periode": per, "n": len(r),
                     "short15_bps": r.mean()*1e4,
                     "t": r.mean()/(r.std(ddof=1)/np.sqrt(len(r))),
                     "net_bps": (r.mean()-0.0019)*1e4,
                     "hit%": (r > 0).mean()*100,
                     "MAE_short_bps": -dd["mfe_15"].mean()*1e4})
print(pd.DataFrame(rows).round(1).to_string(index=False))

print("\n=== 3. Le meilleur bucket, mois par mois (short 15m, vol_mult>25) ===")
s = ev[ev.vol_mult > 25]
g = s.groupby("mois")
print(pd.DataFrame({"n": g.size(),
                    "short15_bps": (-g.fwd_15.mean()*1e4).round(0),
                    "short30_bps": (-g.fwd_30.mean()*1e4).round(0),
                    "MAE_bps": (-g.mfe_15.mean()*1e4).round(0)}).to_string())

print("\n=== 4. Horizon optimal du fade (vol_mult>25, hors oct25) ===")
s2 = s[s.mois != "2025-10"]
rows = []
for h in (3, 5, 10, 15, 30, 60, 120):
    r = -s2[f"fwd_{h}"].dropna()
    rows.append({"h": h, "n": len(r), "short_bps": r.mean()*1e4,
                 "t": r.mean()/(r.std(ddof=1)/np.sqrt(len(r))),
                 "med_bps": r.median()*1e4, "hit%": (r > 0).mean()*100,
                 "MAE_moy_bps": -s2[f"mfe_{h}"].mean()*1e4,
                 "MAE_p90_bps": -s2[f"mfe_{h}"].quantile(.90)*1e4})
print(pd.DataFrame(rows).round(1).to_string(index=False))
