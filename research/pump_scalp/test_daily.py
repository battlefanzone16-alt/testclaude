"""Le pump existe-t-il a un autre horizon que le scalp ?

La conclusion intraday est negative. Question naturelle : le phenomene que
decrit l'utilisateur (ZEC, ARB...) est-il simplement trop LENT pour un scalp ?
On refait exactement la meme event study, en journalier : apres un gros jour de
pump, que font les jours suivants ? Meme univers, memes garde-fous (consistance
mensuelle, IS/OOS). Cout journalier : un aller-retour taker, 9 bps.
"""
import numpy as np, pandas as pd, bvision
pd.set_option("display.width", 210)
START, END = "2025-09-01", "2026-09-01"
COST = 0.0009

syms = [s.strip() for s in open("universe.txt") if s.strip()]
rows = []
for s in syms:
    df = bvision.fetch(s, "1d", START, END)
    if len(df) < 60: continue
    c = df["close"].astype("float64"); o = df["open"].astype("float64")
    r1 = c / c.shift(1) - 1.0
    qv = df["quote_volume"].astype("float64")
    volmult = qv / qv.rolling(30).median().shift(1)
    sig = pd.DataFrame({"symbol": s, "date": df.index, "r1": r1.to_numpy(),
                        "volmult": volmult.to_numpy(),
                        "px": c.to_numpy()})
    for h in (1, 2, 3, 5, 10):
        # entree a l'OUVERTURE du lendemain, pas a la cloture du jour du signal
        sig[f"fwd_{h}"] = (o.shift(-1-h) / o.shift(-1) - 1.0).to_numpy()
    rows.append(sig)

d = pd.concat(rows, ignore_index=True).dropna(subset=["r1", "volmult"])
d["entry_time"] = pd.to_datetime(d["date"])
print(f"{len(d)} observations jour-symbole")

def stats(sub, lab, cost=COST):
    out = []
    for h in (1, 2, 3, 5, 10):
        r = sub[f"fwd_{h}"].dropna()
        if len(r) < 60: continue
        m = sub.groupby(sub.entry_time.dt.to_period("M"))[f"fwd_{h}"].mean()*1e4
        out.append({"filtre": lab, "h_j": h, "n": len(r), "moy_bps": r.mean()*1e4,
                    "net_bps": (r.mean()-cost)*1e4,
                    "t": r.mean()/(r.std(ddof=1)/np.sqrt(len(r))),
                    "med_mois": m.median(), "mois_pos": f"{(m>0).sum()}/{len(m)}",
                    "IS": sub[sub.entry_time<"2026-03-01"][f"fwd_{h}"].mean()*1e4,
                    "OOS": sub[sub.entry_time>="2026-03-01"][f"fwd_{h}"].mean()*1e4})
    return out

res = []
res += stats(d[d.r1 > 0.15], "pump jour > +15%")
res += stats(d[(d.r1 > 0.15) & (d.volmult > 3)], "pump > +15% + volume x3")
res += stats(d[d.r1 > 0.30], "pump jour > +30%")
res += stats(d[d.r1 < -0.15], "dump jour < -15% (controle)")
t = pd.DataFrame(res); t[t.select_dtypes("number").columns] = t.select_dtypes("number").round(1)
print(t.to_string(index=False))

# --- Caracterisation du seul lead survivant : la retombee post-pump ---------
print("\n" + "="*95)
print("LE SEUL EFFET QUI SURVIT : retombee apres un pump journalier (>+15%)")
p = d[d.r1 > 0.15].dropna(subset=["fwd_10"])
r = p["fwd_10"]
print(f"\nn={len(r)} | horizon 10 jours | rendement du TOKEN (un short gagne l'oppose)")
q = r.quantile([.01,.05,.10,.25,.50,.75,.90,.95,.99])
print("distribution (%) :", {f"p{int(k*100)}": round(v*100,1) for k,v in q.items()})
print(f"moyenne {r.mean()*100:.1f}% | mediane {r.median()*100:.1f}% | "
      f"pire cas pour un short : +{r.max()*100:.0f}%")
print(f"part des cas ou le token gagne encore >50% en 10j : {(r>0.5).mean()*100:.1f}%")
print(f"part des cas ou le token gagne encore >100% en 10j : {(r>1.0).mean()*100:.1f}%")
m = p.groupby(p.entry_time.dt.to_period("M"))["fwd_10"].mean()*100
print("\nmoyenne mensuelle du token (%, un short gagne l'oppose) :")
print(m.round(1).to_string())
print("\nNOTE : un short perp encaisse aussi le funding, positif pendant un pump,")
print("donc payé AU short. C'est un vent arriere - mais il ne compense jamais")
print("une queue a +200%. Le dimensionnement, pas le signal, est le sujet ici.")
