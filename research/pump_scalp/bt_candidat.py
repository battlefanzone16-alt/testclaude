"""Le candidat 'seul + z>4' passe au moteur de portefeuille reel.

Une moyenne de rendement forward n'est pas un P&L. Ici : stop, trailing, time
stop, 3 positions simultanees, couts taker, et convention intra-barre
conservatrice. Plus un test de permutation sur les EPISODES, parce que le
t-stat classique suppose des observations independantes que ces evenements
n'ont pas.
"""
import itertools
import numpy as np, pandas as pd
from simulate import ExitRules, portfolio
from simulate_vec import simulate_batch, net
from evaluate2 import episodes
pd.set_option("display.width", 220)

tail = pd.read_parquet("events_tail.parquet"); tail["entry_time"] = pd.to_datetime(tail["entry_time"])
br = pd.read_parquet("events_breadth.parquet"); br["entry_time"] = pd.to_datetime(br["entry_time"])
key = ["symbol", "entry_time"]
tail = tail.merge(br[key + ["breadth_z2", "mkt_r5"]], on=key, how="left")
z = np.load("paths_tail.npz")
O, H, L, ok = z["o"].astype("float64"), z["h"].astype("float64"), z["l"].astype("float64"), z["ok"]

cand = ok & (tail.breadth_z2.to_numpy() < 0.01) & (tail.z_burst.to_numpy() > 4)
print(f"candidat : {cand.sum()} evenements\n")
risk_all = np.clip(tail["sigma_ref"].to_numpy()*np.sqrt(5.)*4.0, 0.003, 0.15)

def bt(mask, rules, label):
    idx = np.flatnonzero(mask)
    ret, ebar, why = simulate_batch(O[idx], H[idx], L[idx], risk_all[idx], rules)
    t = pd.DataFrame({"symbol": tail.symbol.to_numpy()[idx], "entry_time": tail.entry_time.to_numpy()[idx],
                      "hold": ebar, "brut": ret, "net": net(ret, rules),
                      "z": tail.z_burst.to_numpy()[idx]}).dropna(subset=["brut"])
    t["exit_time"] = t.entry_time + pd.to_timedelta(t.hold, unit="m")
    t = t.sort_values(["entry_time","z"], ascending=[True,False]).reset_index(drop=True)
    t = t[portfolio(t, max_concurrent=3)]
    if len(t) < 40: return None
    r = t.net.to_numpy()
    t["_ep"] = episodes(t.entry_time)
    ep = t.groupby("_ep").agg(r=("net","mean"), t0=("entry_time","first"))
    er = ep.r.to_numpy()
    m = ep.groupby(ep.t0.dt.to_period("M")).r.mean()*1e4
    eq = np.cumprod(1 + r*0.05)
    return {"regle": label, "n": len(r), "n_ep": len(er), "n/j": round(len(r)/365,2),
            "brut_bps": round(t.brut.mean()*1e4,1), "net_bps": round(r.mean()*1e4,1),
            "net_EP_bps": round(er.mean()*1e4,1),
            "t_EP": round(er.mean()/(er.std(ddof=1)/np.sqrt(len(er))),2),
            "win%": round((r>0).mean()*100,1), "mois_pos": f"{int((m>0).sum())}/{len(m)}",
            "IS": round(ep[ep.t0<'2026-03-01'].r.mean()*1e4,1),
            "OOS": round(ep[ep.t0>='2026-03-01'].r.mean()*1e4,1),
            "eq_5pct": round(float(eq[-1]),3)}

rows = []
for hold in (60, 120, 180, 240, 360):
    for trail, arm in itertools.product([1.5, 2.5], [0.5, 1.5]):
        r = bt(cand, ExitRules(max_hold=hold, stop_k=1.0, trail_k=trail, arm_at=arm),
               f"hold{hold} trail{trail} arm{arm}")
        if r: rows.append(r)
d = pd.DataFrame(rows).sort_values("net_EP_bps", ascending=False)
print(d.to_string(index=False))
print(f"\n{(d.net_EP_bps>0).sum()}/{len(d)} regles positives en net par episode ; "
      f"{((d.IS>0)&(d.OOS>0)).sum()}/{len(d)} positives en IS ET en OOS")
d.to_csv("bt_candidat.csv", index=False)
