"""Le signal survit-il au retrait du marche, et hors du mois d'octobre 2025 ?"""
import numpy as np, pandas as pd
pd.set_option("display.width", 220)
HZ = [15, 30, 60, 120]

ev = pd.read_parquet("events_k5_btc.parquet")
ev["entry_time"] = pd.to_datetime(ev["entry_time"])
ev["mois"] = ev.entry_time.dt.to_period("M")

def tab(d, label):
    rows = []
    for h in HZ:
        for kind in ("fwd", "res"):
            r = d[f"{kind}_{h}"].dropna()
            if len(r) < 30: continue
            rows.append({"h": h, "type": "brut" if kind == "fwd" else "residu",
                         "n": len(r), "moy_bps": r.mean()*1e4,
                         "t": r.mean()/(r.std(ddof=1)/np.sqrt(len(r)))})
    print(f"\n--- {label} (n={len(d)}) ---")
    print(pd.DataFrame(rows).round(1).to_string(index=False))

t = ev[ev.r_burst > 0.05]
tab(t, "r_burst>5% : TOUTE LA PERIODE")
tab(t[t.mois != "2025-10"], "r_burst>5% : HORS OCTOBRE 2025")
tab(ev[ev.r_burst > 0.08], "r_burst>8% : toute la periode")
tab(ev[(ev.r_burst > 0.08) & (ev.mois != "2025-10")], "r_burst>8% : hors octobre 2025")

print("\n" + "="*90)
print("Le bucket 'BTC monte aussi' : effet propre ou simple beta ?")
b = t[t.r_btc > 0.001]
tab(b, "r_burst>5% ET r_btc>+0.1%")
tab(b[b.mois != "2025-10"], "r_burst>5% ET r_btc>+0.1% : hors octobre 2025")

print("\n" + "="*90)
print("RESIDU par mois (r_burst>5%, horizon 60m)")
g = t.groupby("mois")["res_60"]
print(pd.DataFrame({"n": g.size(), "res60_bps": (g.mean()*1e4).round(0),
                    "brut60_bps": (t.groupby("mois")["fwd_60"].mean()*1e4).round(0)}).to_string())
