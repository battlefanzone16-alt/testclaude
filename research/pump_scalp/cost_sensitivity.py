"""A quel niveau de friction la strategie basculerait-elle ?

C'est la question utile. Le gisement brut existe (~+19 bps par trade) ; il se
trouve qu'il fait exactement la taille du peage. Ce tableau dit quelle qualite
d'execution il faudrait pour que le reste soit positif - et donc si c'est un
probleme d'execution ou un probleme d'alpha.
"""
import numpy as np, pandas as pd
from simulate import ExitRules, portfolio
from simulate_vec import simulate_batch, RAISONS
pd.set_option("display.width", 200)

ev = pd.read_parquet("events_tail.parquet"); ev["entry_time"] = pd.to_datetime(ev["entry_time"])
z = np.load("paths_tail.npz")
O, H, L, ok = z["o"].astype("float64"), z["h"].astype("float64"), z["l"].astype("float64"), z["ok"]
risk = np.clip(ev["sigma_ref"].to_numpy()*np.sqrt(5.)*4.0, 0.003, 0.15)

rules = ExitRules(max_hold=240, stop_k=1.0, trail_k=2.0, arm_at=0.5)
idx = np.flatnonzero(ok)
ret, ebar, why = simulate_batch(O[idx], H[idx], L[idx], risk[idx], rules)
t = pd.DataFrame({"symbol": ev.symbol.to_numpy()[idx], "entry_time": ev.entry_time.to_numpy()[idx],
                  "hold": ebar, "brut": ret, "z": ev.z_burst.to_numpy()[idx]}).dropna(subset=["brut"])
t["exit_time"] = t.entry_time + pd.to_timedelta(t.hold, unit="m")
t = t.sort_values(["entry_time","z"], ascending=[True,False]).reset_index(drop=True)
t = t[portfolio(t, max_concurrent=3)]
g = t.brut.to_numpy()
print(f"Meilleure variante de la grille : {len(g)} trades, brut moyen {g.mean()*1e4:.1f} bps\n")

rows = []
for lab, per_side in [("maker/maker (irrealiste ici)", 2.0),
                      ("maker entree + taker sortie", (2.0+4.5)/2),
                      ("taker/taker, zero slippage", 4.5),
                      ("taker + 2 bps slippage", 6.5),
                      ("taker + 5 bps slippage (hypothese de base)", 9.5),
                      ("taker + 10 bps slippage", 14.5)]:
    c = per_side/1e4
    net = (1+g)*(1-c)/(1+c) - 1
    rows.append({"execution": lab, "cout_AR_bps": per_side*2,
                 "net_bps": net.mean()*1e4, "t": net.mean()/(net.std(ddof=1)/np.sqrt(len(net))),
                 "equity_25pct": float(np.cumprod(1+net*0.25)[-1])})
d = pd.DataFrame(rows); d[d.select_dtypes("number").columns] = d.select_dtypes("number").round(2)
print(d.to_string(index=False))
be = g.mean()/2*1e4
print(f"\n-> Seuil de rentabilite : {be:.1f} bps par cote ({be*2:.1f} bps aller-retour).")
print(f"   Le taker Binance seul en coute deja 4.5 ; il resterait {be-4.5:.1f} bps")
print( "   par cote pour absorber TOUT le slippage d'entree dans une bougie verticale.")
