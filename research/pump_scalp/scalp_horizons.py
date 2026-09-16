"""Le resultat a l'horizon demande : des positions de 1 h, 2 h, 3 h.

Ce fichier ne teste rien de neuf. Il re-presente le coeur de l'etude decoupe
par DUREE DE DETENTION, parce que le rapport enterrait cette lecture sous une
section sur l'effet journalier qui n'etait qu'un aparte.
"""
import itertools
import numpy as np, pandas as pd
from simulate import ExitRules, portfolio
from simulate_vec import simulate_batch, net, RAISONS
pd.set_option("display.width", 220)

ev = pd.read_parquet("events_tail.parquet"); ev["entry_time"] = pd.to_datetime(ev["entry_time"])
z = np.load("paths_tail.npz")
O, H, L, ok = z["o"].astype("float64"), z["h"].astype("float64"), z["l"].astype("float64"), z["ok"]
idx = np.flatnonzero(ok)

def run(rules, risk, label):
    ret, ebar, why = simulate_batch(O[idx], H[idx], L[idx], risk[idx], rules)
    t = pd.DataFrame({"symbol": ev.symbol.to_numpy()[idx], "entry_time": ev.entry_time.to_numpy()[idx],
                      "hold": ebar, "brut": ret, "net": net(ret, rules),
                      "z": ev.z_burst.to_numpy()[idx]}).dropna(subset=["brut"])
    t["exit_time"] = t.entry_time + pd.to_timedelta(t.hold, unit="m")
    t = t.sort_values(["entry_time", "z"], ascending=[True, False]).reset_index(drop=True)
    t = t[portfolio(t, max_concurrent=3)]
    r = t.net.to_numpy()
    if len(r) < 50: return None
    m = t.groupby(t.entry_time.dt.to_period("M"))["net"].mean()*1e4
    j10 = t.entry_time.dt.normalize() == "2025-10-10"
    return {"regle": label, "n": len(r), "duree_med_min": int(t.hold.median()),
            "brut_bps": t.brut.mean()*1e4, "net_bps": r.mean()*1e4,
            "t": r.mean()/(r.std(ddof=1)/np.sqrt(len(r))),
            "win%": (r > 0).mean()*100, "mois_pos": f"{int((m>0).sum())}/{len(m)}",
            "net_sans_10oct": r[~j10.to_numpy()].mean()*1e4,
            "OOS_bps": t[t.entry_time >= "2026-03-01"].net.mean()*1e4}

print("SCALP DE PUMP — resultat par duree maximale de detention")
print("(long apres ignition, 3 positions max, taker 4,5 bps + 5 bps de slippage par cote)\n")
rows = []
for hold, hl in [(60, "1 h"), (120, "2 h"), (180, "3 h"), (240, "4 h")]:
    for mode, mult, ml in [("sigma", 4.0, "stop serre"), ("sigma", 8.0, "stop large")]:
        u = ev["sigma_ref"].to_numpy()*np.sqrt(5.) if mode == "sigma" else ev["r_burst"].to_numpy()
        risk = np.clip(u*mult, 0.003, 0.15)
        for trail, arm in itertools.product([1.0, 2.0], [0.5, 1.5]):
            r = run(ExitRules(max_hold=hold, stop_k=1.0, trail_k=trail, arm_at=arm), risk,
                    f"{hl} / {ml} / trail {trail} / arm {arm}")
            if r: rows.append(r)
d = pd.DataFrame(rows)
d["duree"] = d.regle.str.split(" /").str[0]

print("### Meilleure regle pour chaque duree")
best = d.loc[d.groupby("duree").net_bps.idxmax()].sort_values("duree")
b = best.copy(); b[b.select_dtypes("number").columns] = b.select_dtypes("number").round(1)
print(b.drop(columns="duree").to_string(index=False))

print("\n### Toutes les regles, agregees par duree")
g = d.groupby("duree")
agg = pd.DataFrame({"n_regles": g.size(),
                    "brut_median": g.brut_bps.median().round(1),
                    "net_median": g.net_bps.median().round(1),
                    "net_max": g.net_bps.max().round(1),
                    "regles_net_positives": g.net_bps.apply(lambda x: f"{(x>0).sum()}/{len(x)}"),
                    "net_median_sans_10oct": g.net_sans_10oct.median().round(1),
                    "OOS_median": g.OOS_bps.median().round(1)})
print(agg.to_string())
d.to_csv("scalp_par_duree.csv", index=False)
