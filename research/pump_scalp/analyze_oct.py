"""Exclure le 10 octobre, pas tout octobre.

Le 10 octobre 2025 (cascade de liquidations) porte a lui seul 74% de l'edge du
mois. Exclure le mois entier etait une amputation trop large : elle jetait 29
jours normaux avec les 2 jours anormaux. On refait donc la mesure avec des
exclusions de plus en plus fines, pour voir si l'edge tient une fois l'anomalie
retiree - et elle seule.
"""
import numpy as np, pandas as pd
pd.set_option("display.width", 210)
COST = 0.0019

ev = pd.read_parquet("events_k5_btc.parquet")
ev["entry_time"] = pd.to_datetime(ev["entry_time"])
ev["jour"] = ev.entry_time.dt.normalize()

EXCL = {
    "tout inclus": [],
    "sans le 10 oct": ["2025-10-10"],
    "sans 10-11 oct": ["2025-10-10", "2025-10-11"],
    "sans 8-13 oct (fenetre cascade)": pd.date_range("2025-10-08", "2025-10-13").strftime("%Y-%m-%d").tolist(),
}

for thr in (0.05, 0.08):
    print(f"\n{'='*100}\nr_burst > {thr:.0%}")
    rows = []
    for lab, days in EXCL.items():
        d = ev[(ev.r_burst > thr) & (~ev.jour.isin(pd.to_datetime(days)))]
        for h in (30, 60, 120):
            r = d[f"fwd_{h}"].dropna()
            m = d.groupby(d.entry_time.dt.to_period("M"))[f"fwd_{h}"].mean()*1e4
            rows.append({"exclusion": lab, "h": h, "n": len(r),
                         "moy_bps": r.mean()*1e4, "net_bps": (r.mean()-COST)*1e4,
                         "t": r.mean()/(r.std(ddof=1)/np.sqrt(len(r))),
                         "med_mois": m.median(), "mois_pos": f"{(m>0).sum()}/{len(m)}",
                         "IS": d[d.entry_time<"2026-03-01"][f"fwd_{h}"].mean()*1e4,
                         "OOS": d[d.entry_time>="2026-03-01"][f"fwd_{h}"].mean()*1e4})
    t = pd.DataFrame(rows).sort_values(["h", "exclusion"])
    t[t.select_dtypes("number").columns] = t.select_dtypes("number").round(1)
    print(t.to_string(index=False))

# Le mois d'octobre AMPUTE du seul 10 : redevient-il un mois ordinaire ?
print(f"\n{'='*100}\nOctobre 2025 sans le 10 : un mois ordinaire ?")
o = ev[(ev.entry_time >= "2025-10-01") & (ev.entry_time < "2025-11-01") & (ev.r_burst > 0.05)]
for lab, d in [("octobre entier", o), ("octobre sans le 10", o[o.jour != "2025-10-10"])]:
    r = d["fwd_60"]
    print(f"  {lab:<22} n={len(r):>4}  moy {r.mean()*1e4:>7.1f} bps  med {r.median()*1e4:>6.1f}")
autres = ev[(ev.r_burst > 0.05) & (ev.entry_time.dt.to_period("M") != pd.Period("2025-10"))]
print(f"  {'les 11 autres mois':<22} n={len(autres):>4}  moy {autres.fwd_60.mean()*1e4:>7.1f} bps")

# Combien de ces 152 evenements un portefeuille reel aurait-il pu prendre ?
d10 = ev[(ev.jour == "2025-10-10") & (ev.r_burst > 0.05)]
print(f"\nLe 10 octobre : {len(d10)} signaux sur {d10.symbol.nunique()} symboles.")
h = d10.entry_time.dt.hour.value_counts().sort_index()
print("  repartition horaire :", dict(h[h > 3]))

# --- Ce qu'un portefeuille reel aurait reellement pu prendre le 10 octobre ---
print(f"\n{'='*100}\nL'anomalie etait-elle seulement CAPTURABLE ?")
from simulate import ExitRules, portfolio
from simulate_vec import simulate_batch, net, RAISONS
evt = pd.read_parquet("events_tail.parquet"); evt["entry_time"] = pd.to_datetime(evt["entry_time"])
z = np.load("paths_tail.npz")
O, H, L, ok = z["o"].astype("float64"), z["h"].astype("float64"), z["l"].astype("float64"), z["ok"]
risk = np.clip(evt["sigma_ref"].to_numpy()*np.sqrt(5.)*4.0, 0.003, 0.15)
rules = ExitRules(max_hold=240, stop_k=1.0, trail_k=2.0, arm_at=0.5)
idx = np.flatnonzero(ok)
ret, ebar, why = simulate_batch(O[idx], H[idx], L[idx], risk[idx], rules)
t = pd.DataFrame({"symbol": evt.symbol.to_numpy()[idx], "entry_time": evt.entry_time.to_numpy()[idx],
                  "hold": ebar, "brut": ret, "net": net(ret, rules),
                  "z": evt.z_burst.to_numpy()[idx]}).dropna(subset=["brut"])
t["exit_time"] = t.entry_time + pd.to_timedelta(t.hold, unit="m")
t = t.sort_values(["entry_time", "z"], ascending=[True, False]).reset_index(drop=True)
pris = t[portfolio(t, max_concurrent=3)]
j10 = pris[pris.entry_time.dt.normalize() == "2025-10-10"]
sig10 = t[t.entry_time.dt.normalize() == "2025-10-10"]
print(f"  signaux emis le 10 oct : {len(sig10)}  ->  reellement pris (3 slots) : {len(j10)}")
print(f"  P&L net du 10 oct : {j10.net.sum()*100:.2f} % de capital (a 25%/trade : "
      f"{j10.net.sum()*25:.2f} %)")
print(f"  P&L net des 364 autres jours : {(pris.net.sum()-j10.net.sum())*100:.2f} %")
print(f"  -> le 10 oct represente {j10.net.sum()/pris.net.sum()*100:.0f} % du P&L total "
      f"pour {len(j10)/len(pris)*100:.1f} % des trades")
